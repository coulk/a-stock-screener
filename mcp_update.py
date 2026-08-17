# -*- coding: utf-8 -*-
"""
用 stock-mcp-server（GitHub: 1018053166/stock-mcp-server）抓取当日实时行情，
为 data.json 的结果补充/校验"较上一日涨跌幅"（pct_chg）与总市值（mktcap）。

MCP 工具：get_stock_realtime / batch_get_stocks / get_rank_list / get_market_overview
数据源：东方财富 push2 接口（需大陆网络；GitHub Actions 海外环境不可用，仅本地使用）。

用法：
  python mcp_update.py                 # 用 MCP 批量刷新 data.json 中结果的实时涨跌幅与市值
  python mcp_update.py --market        # 额外打印市场概况（三大指数）
"""
import os
import sys
import json
import argparse
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))


def mcp_call(name, args=None, timeout=40):
    """通过 stdio 调用 MCP 工具，返回解析后的 content[0].text JSON"""
    script = os.path.join(HERE, 'mcp_call.mjs')
    env = dict(os.environ)
    env['MCP_TOOL'] = name
    env['MCP_ARGS'] = json.dumps(args or {})
    r = subprocess.run(['node', script], capture_output=True, text=True,
                       encoding='utf-8', timeout=timeout, env=env)
    if r.returncode != 0:
        raise RuntimeError(f'MCP 调用失败: {r.stderr[:200]}')
    return json.loads(r.stdout)


def main():
    parser = argparse.ArgumentParser(description='用 stock-mcp-server 补充实时涨跌幅与总市值')
    parser.add_argument('--market', action='store_true', help='打印市场概况')
    parser.add_argument('--out', default='data.json')
    args = parser.parse_args()

    if args.market:
        ov = mcp_call('get_market_overview')
        for k in ('shanghai', 'shenzhen', 'chinext'):
            d = ov.get(k, {})
            print(f'{d.get("name", k)}: {d.get("currentPrice")} ({d.get("changePercent")}%)')
        print()

    with open(os.path.join(HERE, args.out), encoding='utf-8-sig') as f:
        data = json.load(f)
    codes = [r['code'] for r in data.get('results', [])]
    print(f'待刷新 {len(codes)} 只实时行情（逐只调用，防限流）...')
    updated = 0
    for i, code in enumerate(codes):
        try:
            q = mcp_call('get_stock_realtime', {'stockCode': code}, timeout=30)
        except Exception as e:
            if i % 10 == 0:
                print(f'  {i}/{len(codes)} (跳过 {code}: {str(e)[:50]})')
            continue
        if isinstance(q, dict) and q.get('stockCode'):
            pct = q.get('changePercent')
            price = q.get('currentPrice')
            prev = q.get('previousClose')
            tcap = q.get('totalMarketCap')  # 东财总市值（元）
            for r in data.get('results', []):
                if r['code'] == code:
                    if pct is not None:
                        r['pct_chg'] = round(float(pct), 2)
                        r['price'] = round(float(price), 2) if price else r['price']
                        r['prev_close'] = round(float(prev), 2) if prev else r.get('prev_close')
                    if tcap:
                        # 东财 push2 总市值单位为元；data.json 统一存亿元
                        r['mktcap'] = round(float(tcap) / 1e8, 2)
                    updated += 1
        if (i + 1) % 20 == 0 or i + 1 == len(codes):
            print(f'  {i + 1}/{len(codes)}')

    with open(os.path.join(HERE, args.out), 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f'✅ 已刷新 {updated} 只实时涨跌幅/市值 -> {args.out}')


if __name__ == '__main__':
    main()
