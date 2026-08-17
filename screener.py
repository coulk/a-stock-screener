# -*- coding: utf-8 -*-
"""
A股 20 日线回踩选股引擎（全市场沪深主板，每日更新）
=====================================================
策略要点（用户当前会话筛选体系）：
  1. 趋势：MA20 向上或刚拐头（含上涨转折），收盘价在 MA20 上方
  2. 回踩：近 3 日内最低价触及 MA20 附近（上方 0~5% 内）
  3. 收盘确认：盘中跌破不算数，最后收盘须收回 MA20 上方（close >= MA20）
  4. 第一次回踩最值钱：自 MA20 拐头以来，此前无收盘跌破/贴近 MA20 记录
  5. 必须缩量：回踩日成交量 < 前 5 日均量 × 80%
  6. 斜率越大越好：MA20 近 5 日变化率，作为排序与评分依据
  7. 板块共振：板块等权指数 MA20 走平/向上 + 板块收盘贴近板块MA20（调整尾声）→ 加分

数据源多源降级（本地与 GitHub Actions 海外环境均可用）：
  全市场快照：stock_zh_a_spot_em(东财) -> stock_zh_a_spot(新浪) -> 腾讯 qt.gtimg.cn 批量
  个股日K：Yahoo chart API -> quotes.sina.cn 直连 -> fetch_history_fallback(腾讯/新浪/雪球/东财) -> akshare 东财
  板块映射：stock_board_industry_name_em(东财) -> stock_sector_spot(新浪) -> 无（板块共振降级为数据不足）

用法：
  python screener.py                      # 生成 data.json
  python screener.py --min-amount 5e8     # 覆盖成交额粗筛阈值
"""
import os
import sys
import json
import time
import argparse
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

for k in ['http_proxy', 'https_proxy', 'HTTP_PROXY', 'HTTPS_PROXY']:
    os.environ.pop(k, None)
os.environ['NO_PROXY'] = '*'

import requests
import pandas as pd
import numpy as np

try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass

# 多源降级数据链路（腾讯→新浪→雪球→东财），与 skill 复用
_SCRIPTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'scripts')
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)
try:
    import fetch_history_fallback as fhf
except Exception:
    fhf = None

# ---------------- 参数 ----------------
KLINE_DAYS = 90           # 拉取K线数量（约90交易日，MA20+斜率+拐点判定足够）
MIN_AMOUNT = 2e8          # 粗筛：日成交额 >= 2亿（排除流动性差）
MIN_MARKET_CAP = 5e9      # 粗筛：总市值 >= 50亿（排除仙股，回踩体系偏活跃票）
MAX_CHG = 9.8             # 粗筛：当日涨跌幅绝对值上限（排除涨停/跌停无法交易）
TOUCH_PCT = 0.05          # 回踩触及容差：最低价 <= MA20*(1+5%)
VOL_RATIO = 0.80          # 缩量阈值：回踩日量 < 前5日均量*80%
SLOPE_DAYS = 5            # MA20 斜率窗口
MAX_WORKERS = 8           # 并发数（quotes.sina.cn 响应快，可承受更高并发）
REQUEST_GAP = 0.25        # 每请求最小间隔秒数（quotes.sina.cn 快，0.25s 足够）

MAINBOARD_PREFIXES = ('600', '601', '603', '605', '000', '001', '002', '003')
_UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}


def is_mainboard(code):
    c = str(code).zfill(6)
    return c.startswith(MAINBOARD_PREFIXES)


def is_st(name):
    return 'ST' in str(name).upper()


def to_symbol(code):
    c = str(code).zfill(6)
    return f"sh{c}" if c.startswith('6') else f"sz{c}"


# ---------------- 全市场快照（多源降级） ----------------
def _with_timeout(fn, timeout):
    """在线程中运行 fn，超时返回 None（避免上游接口卡死；不等待后台线程）"""
    ex = ThreadPoolExecutor(max_workers=1)
    fut = ex.submit(fn)
    try:
        return fut.result(timeout=timeout)
    except Exception:
        return None
    finally:
        ex.shutdown(wait=False)


def _spot_from_tencent():
    """腾讯 qt.gtimg.cn 批量快照（主源：大陆/海外均可访问）"""
    import akshare as ak
    codes = ak.stock_info_a_code_name()
    all_codes = [str(c).zfill(6) for c in codes['code']]
    rows = []
    batch = 50
    for i in range(0, len(all_codes), batch):
        chunk = all_codes[i:i + batch]
        syms = ','.join(to_symbol(c) for c in chunk)
        try:
            r = requests.get(f"https://qt.gtimg.cn/q={syms}",
                             headers={**_UA, 'Referer': 'https://gu.qq.com/'}, timeout=10)
        except Exception:
            continue
        r.encoding = 'gbk'
        for line in r.text.split(';'):
            line = line.strip()
            if not line.startswith('v_'):
                continue
            body = line.split('="', 1)[-1].rstrip('"')
            f = body.split('~')
            if len(f) < 46:
                continue
            try:
                rows.append({
                    'code': str(f[2]).zfill(6),
                    'name': f[1],
                    'price': float(f[3]),
                    'chg_pct': float(f[32]),
                    'amount': float(f[37]) * 1e4,   # 万元 -> 元
                    'mktcap': float(f[45]) * 1e8,   # 亿元 -> 元
                })
            except (ValueError, IndexError):
                continue
        time.sleep(0.05)
    return pd.DataFrame(rows)


def _spot_from_em():
    """东财全市场快照。
    代码列表用 stock_info_a_code_name（push2 域名，单请求全量 5539 只，大陆/海外可用）；
    市值/成交额用 clist 分页补充（失败则降级：仅代码+名称，粗筛市值/成交额跳过）。"""
    import akshare as ak
    import subprocess

    codes = ak.stock_info_a_code_name()
    base = pd.DataFrame({
        'code': codes['code'].astype(str).str.zfill(6),
        'name': codes['name'].astype(str),
    })
    base['price'] = 0.0
    base['chg_pct'] = 0.0
    base['amount'] = 0.0
    base['mktcap'] = 0.0

    # 用 clist 分页补充市值/成交额/涨跌幅（失败则保持 0，粗筛条件会跳过这些列）
    curl_ua = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
               "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    extra = {}
    pn = 1
    total = None
    while pn <= 60:
        url = ("https://push2.eastmoney.com/api/qt/clist/get"
               f"?pn={pn}&pz=100&po=1&np=1&fltt=2&invt=2&fid=f3"
               "&fs=m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23"
               "&fields=f12,f13,f14,f2,f3,f6,f20")
        try:
            r = subprocess.run(['curl', '-s', '--max-time', '15', '-H',
                                f'User-Agent: {curl_ua}', url],
                               capture_output=True, encoding='utf-8', timeout=20)
            j = json.loads(r.stdout)
            data = j.get('data') or {}
            if total is None:
                total = int(data.get('total') or 0)
            diff = data.get('diff') or []
        except Exception:
            break
        if not diff:
            break
        for it in diff:
            try:
                c = str(it.get('f12', '')).zfill(6)
                extra[c] = {
                    'price': float(it.get('f2') or 0),
                    'chg_pct': float(it.get('f3') or 0),
                    'amount': float(it.get('f6') or 0),
                    'mktcap': float(it.get('f20') or 0),
                }
            except (ValueError, TypeError):
                continue
        if len(extra) >= (total or 1):
            break
        pn += 1
        time.sleep(0.8)

    if extra:
        ex = pd.DataFrame(extra).T
        ex.index.name = 'code'
        base = base.set_index('code')
        for col in ['price', 'chg_pct', 'amount', 'mktcap']:
            base[col] = ex[col].reindex(base.index).fillna(0)
        base = base.reset_index()
    return base


def _spot_from_sina():
    """新浪全市场快照"""
    import akshare as ak
    df = ak.stock_zh_a_spot()
    return pd.DataFrame({
        'code': df['代码'].astype(str).str.zfill(6),
        'name': df['名称'].astype(str),
        'price': pd.to_numeric(df['最新价'], errors='coerce'),
        'chg_pct': pd.to_numeric(df['涨跌幅'], errors='coerce'),
        'amount': pd.to_numeric(df['成交额'], errors='coerce'),
        'mktcap': pd.to_numeric(df['总市值'], errors='coerce'),
    })


def get_spot_df():
    """返回 DataFrame[code,name,price,chg_pct,amount,mktcap]。
    数据源顺序：东财 push2 clist（主，单请求全市场）-> 腾讯批量 -> 新浪，均带超时保护"""
    # 1) 东财 push2 clist（主源）
    df = _with_timeout(_spot_from_em, 30)
    if df is not None and not df.empty:
        return df
    # 2) 腾讯批量
    df = _with_timeout(_spot_from_tencent, 90)
    if df is not None and not df.empty:
        return df
    # 3) 新浪
    df = _with_timeout(_spot_from_sina, 30)
    if df is not None and not df.empty:
        return df
    return pd.DataFrame()


# ---------------- 板块映射（多源降级） ----------------
def get_sector_map(codes):
    """返回 {code: 板块名}；失败返回 {}（带超时保护，避免上游卡死）"""
    wanted = {str(c).zfill(6) for c in codes}
    # 1) 东财行业板块
    def _from_em():
        import akshare as ak
        boards = ak.stock_board_industry_name_em()
        mapping = {}
        names = boards['板块名称'].tolist()
        def _one(name):
            try:
                cons = ak.stock_board_industry_cons_em(symbol=name)
                return [(str(c).zfill(6), name) for c in cons['代码']]
            except Exception:
                return []
        with ThreadPoolExecutor(max_workers=4) as ex:
            for fut in as_completed([ex.submit(_one, n) for n in names]):
                for c, n in fut.result():
                    if c in wanted and c not in mapping:
                        mapping[c] = n
        return mapping
    m = _with_timeout(_from_em, 60)
    if m:
        return m
    # 2) 新浪板块
    def _from_sina():
        import akshare as ak
        spot = ak.stock_sector_spot()
        mapping = {}
        for label in spot['label'].tolist():
            try:
                d = ak.stock_sector_detail(sector=label)
                for c in d['code'].astype(str).str.zfill(6):
                    if c in wanted and c not in mapping:
                        mapping[c] = label
            except Exception:
                continue
            time.sleep(0.1)
        return mapping
    m = _with_timeout(_from_sina, 60)
    return m or {}


# ---------------- 个股日K（多源降级） ----------------
def fetch_kline_yahoo(code):
    """Yahoo Finance chart API（GitHub Actions 海外环境可用；大陆被墙）"""
    c = str(code).zfill(6)
    symbol = f"{c}.SS" if c.startswith('6') else f"{c}.SZ"
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=6mo&interval=1d"
    try:
        r = requests.get(url, headers=_UA, timeout=5)
        r.raise_for_status()
        j = r.json()
        res = j['chart']['result'][0]
        ts = res['timestamp']
        q = res['indicators']['quote'][0]
        df = pd.DataFrame({
            'date': pd.to_datetime(ts, unit='s').strftime('%Y-%m-%d'),
            'open': q['open'], 'close': q['close'],
            'high': q['high'], 'low': q['low'], 'volume': q['volume'],
        }).dropna(subset=['close'])
        if len(df) < 30:
            return None
        for col in ['open', 'close', 'high', 'low', 'volume']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        return df.reset_index(drop=True)
    except Exception:
        return None


def fetch_kline_sina_direct(code):
    """quotes.sina.cn 直连（大陆本地可用）"""
    c = str(code).zfill(6)
    symbol = to_symbol(c)
    url = ("https://quotes.sina.cn/cn/api/jsonp_v2.php/var%20_=/CN_MarketDataService.getKLineData"
           f"?symbol={symbol}&scale=240&ma=no&datalen={KLINE_DAYS}")
    try:
        r = requests.get(url, headers={**_UA, 'Referer': 'https://finance.sina.com.cn/'}, timeout=6)
        r.raise_for_status()
        text = r.text
        start = text.find('([')
        end = text.rfind('])')
        if start < 0 or end < 0:
            return None
        data = json.loads(text[start + 1:end + 1])
        if not data:
            return None
        df = pd.DataFrame(data).rename(columns={'day': 'date'})
        df = df[['date', 'open', 'close', 'high', 'low', 'volume']]
        for col in ['open', 'close', 'high', 'low', 'volume']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        df = df.dropna(subset=['close'])
        if len(df) < 30:
            return None
        return df.reset_index(drop=True)
    except Exception:
        return None


_tls = threading.local()


def _get_session():
    s = getattr(_tls, 'session', None)
    if s is None and fhf is not None:
        s = fhf._build_session()
        _tls.session = s
    return s


def fetch_kline(code, fast=False):
    """多源降级拉日K。
    fast=True（静态列表/Actions 模式）：仅 quotes.sina.cn + Yahoo，失败快速放弃；
    fast=False（本地调试）：完整降级链 sina→Yahoo→fhf→akshare"""
    c = str(code).zfill(6)
    # 1) quotes.sina.cn（大陆/海外均可用，最快）
    df = fetch_kline_sina_direct(c)
    if df is not None:
        return df
    # 2) Yahoo（海外可用；大陆被墙会快速超时）
    df = fetch_kline_yahoo(c)
    if df is not None:
        return df
    if fast:
        return None
    # 3) fhf 多源（腾讯→新浪→雪球→东财）
    if fhf is not None:
        try:
            session = _get_session()
            norm = fhf.normalize_code(c)
            start = (pd.Timestamp.now() - pd.Timedelta(days=KLINE_DAYS)).strftime('%Y-%m-%d')
            end = pd.Timestamp.now().strftime('%Y-%m-%d')
            df, _src = fhf._fetch_kline_with_fallback(
                session, norm, '1d', KLINE_DAYS, start=start, end=end, retry=1)
            if df is not None and not df.empty and len(df) >= 30:
                df = df.rename(columns={'time': 'date'})
                df = df[['date', 'open', 'close', 'high', 'low', 'volume']].reset_index(drop=True)
                df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
                for col in ['open', 'close', 'high', 'low', 'volume']:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
                return df
        except Exception:
            pass
    # 4) akshare 东财
    try:
        import akshare as ak
        df = ak.stock_zh_a_hist(symbol=c, period='daily',
                                start_date=(pd.Timestamp.now() - pd.Timedelta(days=KLINE_DAYS)).strftime('%Y%m%d'),
                                end_date=pd.Timestamp.now().strftime('%Y%m%d'), adjust='qfq')
        if df is None or len(df) < 30:
            return None
        df = df.rename(columns={'日期': 'date', '开盘': 'open', '收盘': 'close',
                                '最高': 'high', '最低': 'low', '成交量': 'volume'})
        df = df[['date', 'open', 'close', 'high', 'low', 'volume']].reset_index(drop=True)
        for col in ['open', 'close', 'high', 'low', 'volume']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        return df
    except Exception:
        return None


# ---------------- 回踩判定 ----------------
def analyze_stock(code, name, df, mktcap=0.0):
    """返回判定字典；不满足硬条件返回 None。mktcap 为快照总市值（元），透传到结果。"""
    close = df['close'].values.astype(float)
    low = df['low'].values.astype(float)
    vol = df['volume'].values.astype(float)
    dates = df['date'].values

    if len(close) < 25 or np.isnan(close[-1]):
        return None

    ma20 = pd.Series(close).rolling(20).mean().values
    ma20_now = ma20[-1]
    if np.isnan(ma20_now):
        return None
    ma20_prev = ma20[-1 - SLOPE_DAYS]
    slope = (ma20_now / ma20_prev - 1) * 100 if not np.isnan(ma20_prev) and ma20_prev > 0 else 0.0

    # 趋势：MA20 向上（斜率>0）或近5日刚拐头
    ma20_vals = pd.Series(close).rolling(20).mean().dropna().values
    turn = False
    if len(ma20_vals) >= 3:
        for i in range(len(ma20_vals) - SLOPE_DAYS, len(ma20_vals)):
            if i >= 2 and ma20_vals[i] > ma20_vals[i - 1] and ma20_vals[i - 1] <= ma20_vals[i - 2]:
                turn = True
                break
    trend_ok = slope > 0.0 or turn
    if not trend_ok:
        return None

    # 收盘价在 MA20 上方
    if close[-1] < ma20_now:
        return None

    # 回踩：近3日内最低价触及 MA20 附近（含盘中跌破）
    pullback_idx = None
    pullback_low = None
    for j in range(1, 4):
        i = len(close) - j
        if low[i] <= ma20[i] * (1 + TOUCH_PCT):
            pullback_idx = i
            pullback_low = low[i]
            break
    if pullback_idx is None:
        return None

    # 收盘确认：最后交易日收盘收回 MA20 上方
    if close[-1] < ma20_now:
        return None

    dist_pct = (close[-1] / ma20_now - 1) * 100

    # 缩量：回踩日成交量 < 前5日均量*80%
    if pullback_idx >= 5:
        vol_ma5 = np.mean(vol[pullback_idx - 5:pullback_idx])
    else:
        vol_ma5 = np.mean(vol[:pullback_idx])
    vol_ratio = vol[pullback_idx] / vol_ma5 if vol_ma5 > 0 else 9.9
    if vol_ratio >= VOL_RATIO:
        return None

    # 第一次回踩：自最近拐点以来无收盘跌破 MA20*0.995
    pivot = 20
    if len(ma20_vals) >= 3:
        for i in range(len(ma20_vals) - 2, 0, -1):
            if ma20_vals[i] > ma20_vals[i - 1] and ma20_vals[i - 1] <= ma20_vals[i - 2]:
                pivot = i
                break
    pivot_orig = pivot + 19
    is_first = True
    for i in range(pivot_orig, pullback_idx):
        if close[i] < ma20[i] * 0.995:
            is_first = False
            break

    # 较上一日涨跌幅（今日收盘 vs 昨日收盘）
    prev_close = close[-2] if len(close) >= 2 else close[-1]
    pct_chg = (close[-1] / prev_close - 1) * 100 if prev_close > 0 else 0.0

    return {
        'code': str(code).zfill(6),
        'name': name,
        'price': round(float(close[-1]), 2),
        'prev_close': round(float(prev_close), 2),
        'pct_chg': round(float(pct_chg), 2),
        'mktcap': round(float(mktcap or 0) / 1e8, 2),  # 总市值（亿元）
        'ma20': round(float(ma20_now), 2),
        'dist_ma20': round(dist_pct, 2),
        'slope_ma20': round(slope, 2),
        'pullback_date': str(dates[pullback_idx]),
        'vol_ratio': round(vol_ratio, 2),
        'is_first': bool(is_first),
        'is_turn': bool(turn),
    }


# ---------------- 板块共振 ----------------
def build_board_index(klines, sector_map):
    """按板块构建等权指数：{sector: pd.Series(close均值按日期对齐)}"""
    by_sector = {}
    for code, df in klines.items():
        if df is None or len(df) < 30:
            continue
        sec = sector_map.get(code)
        if sec is None:
            continue
        by_sector.setdefault(sec, {})[code] = df.set_index('date')['close']
    out = {}
    for sec, frames in by_sector.items():
        if len(frames) < 5:
            continue
        out[sec] = pd.concat(frames, axis=1).ffill().mean(axis=1)
    return out


def board_resonance(board, slope_days=SLOPE_DAYS):
    if board is None or len(board) < 30:
        return False, 0.0, None
    ma20 = board.rolling(20).mean()
    if np.isnan(ma20.iloc[-1]):
        return False, 0.0, None
    slope = (ma20.iloc[-1] / ma20.iloc[-1 - slope_days] - 1) * 100
    dist = (board.iloc[-1] / ma20.iloc[-1] - 1) * 100
    ok = slope > -0.5 and 0 <= dist <= 5.0
    return ok, round(slope, 2), round(dist, 2)


# ---------------- 主流程 ----------------
def main():
    parser = argparse.ArgumentParser(description='A股20日线回踩选股（全市场沪深主板）')
    parser.add_argument('--min-amount', type=float, default=MIN_AMOUNT, help='粗筛最小成交额（元）')
    parser.add_argument('--min-market-cap', type=float, default=MIN_MARKET_CAP, help='粗筛最小总市值（元）')
    parser.add_argument('--max-workers', type=int, default=MAX_WORKERS)
    parser.add_argument('--out', default='data.json')
    parser.add_argument('--candidates', default='',
                        help='指定候选代码（逗号分隔），跳过全市场快照粗筛（测试用）')
    parser.add_argument('--static-list', default='stock_list.json',
                        help='静态代码列表文件（Actions 海外环境用，跳过联网快照）')
    parser.add_argument('--no-static', action='store_true',
                        help='强制联网获取全市场快照（本地大陆环境）')
    parser.add_argument('--no-sector', action='store_true',
                        help='跳过板块映射（Actions 海外板块源不可用，加速）')
    args = parser.parse_args()

    print('=' * 72)
    print('  A股 20 日线回踩选股（全市场沪深主板）')
    print('=' * 72)

    # 1) 股票池：--candidates 测试模式 或 静态列表 或 全市场快照粗筛
    if args.candidates:
        codes = [c.strip().zfill(6) for c in args.candidates.split(',') if c.strip()]
        spot = pd.DataFrame({'code': codes, 'name': codes, 'price': 0.0,
                             'chg_pct': 0.0, 'amount': 0.0, 'mktcap': 0.0})
        cand = spot
        print(f'🧪 测试模式：指定 {len(codes)} 只候选')
    elif (not args.no_static) and os.path.isfile(args.static_list):
        with open(args.static_list, encoding='utf-8') as f:
            lst = json.load(f)
        spot = pd.DataFrame(lst)
        spot['code'] = spot['code'].astype(str).str.zfill(6)
        for col in ['price', 'chg_pct', 'amount', 'mktcap']:
            if col not in spot.columns:
                spot[col] = 0.0
        spot['price'] = pd.to_numeric(spot['price'], errors='coerce').fillna(0)
        spot['chg_pct'] = pd.to_numeric(spot['chg_pct'], errors='coerce').fillna(0)
        spot['amount'] = pd.to_numeric(spot['amount'], errors='coerce').fillna(0)
        spot['mktcap'] = pd.to_numeric(spot['mktcap'], errors='coerce').fillna(0)
        cand = spot[spot['code'].map(is_mainboard) & ~spot['name'].map(is_st)].copy()
        # 有市值数据则做粗筛压缩候选（加快拉K），无则全主板
        if (cand['mktcap'] > 0).any():
            cand = cand[(cand['mktcap'] >= args.min_market_cap) &
                        (cand['amount'] >= args.min_amount) &
                        (cand['chg_pct'].abs() <= MAX_CHG)]
        cand = cand.drop_duplicates(subset='code')
        print(f'📋 静态列表 {len(spot)} 只 -> 主板+市值/成交额粗筛后候选 {len(cand)} 只')
    else:
        print('⏳ 拉取全市场快照...')
        spot = get_spot_df()
        if spot.empty:
            print('❌ 全市场快照获取失败（所有数据源不可用）')
            return 1
        spot = spot.dropna(subset=['price', 'amount'])
        cand = spot[spot['code'].map(is_mainboard) & ~spot['name'].map(is_st)].copy()
        # 若市值/成交额数据缺失（clist 补充失败降级），跳过这两项粗筛，仅按主板+非ST
        has_amount = bool((cand['amount'].fillna(0) > 0).any())
        if has_amount:
            cand = cand[(cand['amount'] >= args.min_amount) &
                        (cand['mktcap'] >= args.min_market_cap) &
                        (cand['chg_pct'].abs() <= MAX_CHG)]
        else:
            print('⚠️ 市值/成交额数据缺失（clist 降级），跳过市值/成交额粗筛，全主板扫描')
        cand = cand.drop_duplicates(subset='code')
        print(f'📊 全市场 {len(spot)} 只 -> 主板+粗筛后候选 {len(cand)} 只')

    # 2) 板块映射（--no-sector 跳过；海外环境板块源不可用）
    print('⏳ 构建板块映射...')
    if args.no_sector:
        sector_map = {}
        sector_ok = False
        print('  (跳过板块映射 --no-sector)')
    else:
        sector_map = get_sector_map(cand['code'])
        print(f'  板块映射命中 {len(sector_map)} 只')
        sector_ok = len(sector_map) > 0

    # 3) 并发拉日K（fast 模式：静态列表/Actions 仅用 sina+Yahoo 快速源）
    fast_mode = (not args.no_static) or bool(args.candidates)
    print(f'⏳ 拉取日K（并发 {args.max_workers}，{"快速双源" if fast_mode else "完整多源降级"}）...')
    klines = {}
    done = 0
    gap_lock = threading.Lock()
    last_req = [0.0]

    def _throttled_fetch(code):
        with gap_lock:
            wait = last_req[0] + REQUEST_GAP - time.time()
            if wait > 0:
                time.sleep(wait)
            last_req[0] = time.time()
        return fetch_kline(code, fast=fast_mode)

    with ThreadPoolExecutor(max_workers=args.max_workers) as ex:
        futs = {ex.submit(_throttled_fetch, c): c for c in cand['code']}
        for fut in as_completed(futs):
            c = futs[fut]
            klines[c] = fut.result()
            done += 1
            if done % 100 == 0 or done == len(cand):
                print(f'    {done}/{len(cand)} 完成')
    ok_cnt = sum(1 for v in klines.values() if v is not None)
    print(f'✅ K线获取成功: {ok_cnt}/{len(cand)}')

    # 4) 回踩判定
    name_map = dict(zip(cand['code'], cand['name']))
    mktcap_map = dict(zip(cand['code'], pd.to_numeric(cand['mktcap'], errors='coerce').fillna(0)))
    results = []
    for code, df in klines.items():
        if df is None or len(df) < 30:
            continue
        r = analyze_stock(code, name_map.get(code, ''), df, mktcap=mktcap_map.get(code, 0.0))
        if r:
            results.append(r)

    # 5) 板块共振（加分）
    resonance_map = {}
    if sector_ok:
        board_index = build_board_index(klines, sector_map)
        for sec, board in board_index.items():
            ok, b_slope, b_dist = board_resonance(board)
            resonance_map[sec] = {'ok': ok, 'slope': b_slope, 'dist': b_dist}
    for r in results:
        sec = sector_map.get(r['code'])
        r['sector'] = sec or ''
        ok = resonance_map.get(sec, {}).get('ok', False) if sec else False
        r['resonance'] = bool(ok)
        score = 0.0
        score += 30 if r['is_first'] else 0
        score += min(30, max(0, r['slope_ma20'] * 10))
        score += min(15, max(0, (0.80 - r['vol_ratio']) * 30))
        score += min(15, max(0, 5 - abs(r['dist_ma20'])))
        score += 10 if r['resonance'] else 0
        r['score'] = round(score, 1)

    results.sort(key=lambda x: (x['is_first'], x['slope_ma20']), reverse=True)

    # 6) 增量对比：与上次结果比较，标记 status（new=新增 / kept=持续 / broken=趋势破坏）
    history_path = os.path.join(os.path.dirname(os.path.abspath(args.out)), 'history.json')
    prev = {}
    prev_codes = set()
    prev_by_code = {}
    if os.path.isfile(history_path):
        try:
            with open(history_path, encoding='utf-8') as f:
                prev = json.load(f)
            prev_codes = {r['code'] for r in prev.get('results', [])}
            prev_by_code = {r['code']: r for r in prev.get('results', [])}
        except Exception:
            prev = {}
    cur_codes = {r['code'] for r in results}

    now = pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
    for r in results:
        if r['code'] not in prev_codes:
            r['status'] = 'new'          # 新增
        else:
            r['status'] = 'kept'         # 持续
    # 趋势破坏：上次命中、本次不再命中（或本次判定失效）
    broken = []
    for code, pr in prev_by_code.items():
        if code not in cur_codes:
            broken.append({
                'code': code,
                'name': pr.get('name', ''),
                'status': 'broken',
                'last_price': pr.get('price'),
                'last_slope': pr.get('slope_ma20'),
                'last_date': pr.get('pullback_date', ''),
                'last_seen': prev.get('generated_at', ''),
            })
    # 新增/破坏计数
    n_new = sum(1 for r in results if r['status'] == 'new')
    n_broken = len(broken)

    # 7) 输出 data.json（含增量标记）
    data = {
        'generated_at': now,
        'market': '沪深主板',
        'total_spot': int(len(spot)),
        'candidates': int(len(cand)),
        'kline_ok': int(ok_cnt),
        'matched': len(results),
        'new_count': n_new,
        'broken_count': n_broken,
        'prev_date': prev.get('generated_at', ''),
        'params': {
            'min_amount': args.min_amount,
            'min_market_cap': args.min_market_cap,
            'touch_pct': TOUCH_PCT,
            'vol_ratio': VOL_RATIO,
            'slope_days': SLOPE_DAYS,
        },
        'sector_resonance': resonance_map,
        'results': results,
        'broken': broken,
    }
    with open(args.out, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    # 保存本次结果到 history.json（供下次对比）
    with open(history_path, 'w', encoding='utf-8') as f:
        json.dump({'generated_at': now, 'results': results}, f, ensure_ascii=False)
    print(f'\n💾 已保存: {args.out} | 命中 {len(results)} 只 | ➕新增 {n_new} | ➖趋势破坏 {n_broken}')

    # 控制台摘要
    if results:
        print('\n' + '-' * 72)
        print(f'{"code":<8}{"name":<10}{"现价":>8}{"距MA20%":>8}{"斜率%":>7}{"量比":>6}  {"回踩日":<12}{"首次":<4}{"共振":<4}{"评分":>6}')
        for r in results[:30]:
            print(f'{r["code"]:<8}{r["name"]:<10}{r["price"]:>8.2f}{r["dist_ma20"]:>8.2f}'
                  f'{r["slope_ma20"]:>7.2f}{r["vol_ratio"]:>6.2f}  {r["pullback_date"]:<12}'
                  f'{"是" if r["is_first"] else "否":<4}{"✓" if r["resonance"] else "":<4}{r["score"]:>6.1f}')
        print('-' * 72)
    return 0


if __name__ == '__main__':
    sys.exit(main())
