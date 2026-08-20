# -*- coding: utf-8 -*-
"""
本地 A 股数据服务（127.0.0.1）
==============================
由本地程序直接爬东方财富公开接口（push2.eastmoney.com），
标准化返回：市值、行业板块、地区板块、概念板块、现价、涨跌幅、成交额。
供 a-stock-screener 的 local_enrich.py 使用（Agent 只访问 127.0.0.1）。

启动：
  python local_quote_server.py            # 默认 127.0.0.1:8910
  python local_quote_server.py --port 8911

接口：
  GET /api/enrich?codes=600519,000001
    -> {"codes": [{"code","name","price","pct_chg","amount","mktcap","industry","region","concepts"}], "ts": ...}

说明：
  - 快照部分用东财 clist 分页拉全市场（TTL 60s 缓存），返回价格/涨跌幅/成交额/总市值
  - 板块部分逐只调 stock/get 取 f127(行业)/f128(地区)/f129(概念)，带 0.1s 限速
  - 依赖：requests（已随 screener 环境安装）
"""
import os
import sys
import json
import time
import argparse
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

for k in ['http_proxy', 'https_proxy', 'HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'all_proxy']:
    os.environ.pop(k, None)
os.environ['NO_PROXY'] = '*'

import requests

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
EM_UT = 'fa5fd1943c7b386f172d6893dbfba10b'
EM_HOSTS = ['push2.eastmoney.com', 'push2delay.eastmoney.com']  # 主/备域名自动降级

_spot_cache = {'data': None, 'ts': 0.0}
_spot_lock = threading.Lock()
SPOT_TTL = 60  # 秒


def get_spot_map():
    """全市场快照 -> {code: {name, price, chg_pct, amount, mktcap}}（东财 clist 分页）"""
    now = time.time()
    with _spot_lock:
        if _spot_cache['data'] and now - _spot_cache['ts'] < SPOT_TTL:
            return _spot_cache['data']
    m = {}
    pn = 1
    total = None
    while pn <= 100:
        url_path = ('/api/qt/clist/get'
                    f'?pn={pn}&pz=100&po=1&np=1&fltt=2&invt=2&fid=f12'
                    '&fs=m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23'
                    '&fields=f12,f14,f2,f3,f6,f20')
        ok = False
        for host in EM_HOSTS:
            try:
                r = requests.get(f'https://{host}{url_path}',
                                 headers={'User-Agent': UA}, timeout=10)
                j = r.json()
                diff = (j.get('data') or {}).get('diff') or []
                if total is None:
                    total = int((j.get('data') or {}).get('total') or 0)
                if diff:
                    ok = True
                    break
            except Exception:
                continue
        if not ok:
            break
        if not diff:
            break
        for it in diff:
            try:
                c = str(it.get('f12', '')).zfill(6)
                m[c] = {
                    'name': str(it.get('f14') or ''),
                    'price': float(it.get('f2') or 0),
                    'chg_pct': float(it.get('f3') or 0),
                    'amount': float(it.get('f6') or 0),
                    'mktcap': float(it.get('f20') or 0),  # 元
                }
            except (ValueError, TypeError):
                continue
        if len(m) >= (total or 1):
            break
        pn += 1
        time.sleep(0.15)
    with _spot_lock:
        _spot_cache['data'] = m
        _spot_cache['ts'] = time.time()
    return m


def to_secid(code):
    c = str(code).zfill(6)
    return f"1.{c}" if c.startswith(('6', '5')) else f"0.{c}"


def get_boards(code):
    """单只股票板块：f127 行业 / f128 地区 / f129 概念列表"""
    url_path = ('/api/qt/stock/get'
                f'?secid={to_secid(code)}'
                '&fields=f57,f58,f127,f128,f129'
                f'&ut={EM_UT}&fltt=2&invt=2')
    for host in EM_HOSTS:
        try:
            r = requests.get(f'https://{host}{url_path}',
                             headers={'User-Agent': UA}, timeout=8)
            d = (r.json() or {}).get('data') or {}
            if d:
                concepts = [x.strip() for x in str(d.get('f129') or '').split(',') if x.strip()]
                return {
                    'industry': str(d.get('f127') or ''),
                    'region': str(d.get('f128') or ''),
                    'concepts': concepts,
                }
        except Exception:
            continue
    return {'industry': '', 'region': '', 'concepts': []}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == '/health':
            self._json({'ok': True, 'ts': time.strftime('%Y-%m-%d %H:%M:%S')})
            return
        if parsed.path == '/api/enrich':
            q = parse_qs(parsed.query)
            codes = [c.strip().zfill(6) for c in (q.get('codes', ['']))[0].split(',') if c.strip()]
            if not codes:
                self._json({'error': 'codes 参数必填，如 /api/enrich?codes=600519,000001'}, 400)
                return
            spot = get_spot_map()
            out = []
            for i, code in enumerate(codes):
                s = spot.get(code, {})
                b = get_boards(code)
                out.append({
                    'code': code,
                    'name': s.get('name', ''),
                    'price': s.get('price', 0),
                    'pct_chg': s.get('chg_pct', 0),
                    'amount': s.get('amount', 0),
                    'mktcap': round(s.get('mktcap', 0) / 1e8, 2),  # 亿元
                    'industry': b['industry'],
                    'region': b['region'],
                    'concepts': b['concepts'],
                })
                time.sleep(0.1)  # 限速防封
            self._json({'codes': out, 'ts': time.strftime('%Y-%m-%d %H:%M:%S')})
            return
        self._json({'error': 'not found'}, 404)

    def _json(self, obj, status=200):
        body = json.dumps(obj, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main():
    parser = argparse.ArgumentParser(description='本地 A 股数据服务（东财公开接口）')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8910)
    args = parser.parse_args()
    print(f'本地 A 股数据服务启动: http://{args.host}:{args.port} （/api/enrich?codes=600519,000001）')
    ThreadingHTTPServer((args.host, args.port), Handler).serve_forever()


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
