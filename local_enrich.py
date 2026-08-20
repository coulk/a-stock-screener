# -*- coding: utf-8 -*-
"""
local_enrich.py — 用本地数据服务（127.0.0.1:8910）为 data.json 补齐
市值(mktcap)、行业板块(sector)、地区(region)、概念板块(concepts)。

用法：
  python local_enrich.py                    # 默认读取/写回 data.json
  python local_enrich.py --out data.json    # 指定文件
"""
import os
import sys
import json
import argparse
import time
import requests

for k in ['http_proxy', 'https_proxy', 'HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'all_proxy']:
    os.environ.pop(k, None)
os.environ['NO_PROXY'] = '*'

SERVER = os.environ.get('LOCAL_QUOTE_SERVER', 'http://127.0.0.1:8910')
MIN_CAP, MAX_CAP = 50.0, 300.0  # 亿元，后端过滤 50亿～300亿


def enrich(codes, batch=50):
    """分批调用本地服务，返回 {code: 合并数据}"""
    out = {}
    for i in range(0, len(codes), batch):
        chunk = codes[i:i + batch]
        url = f'{SERVER}/api/enrich?codes=' + ','.join(chunk)
        try:
            r = requests.get(url, timeout=120)
            r.raise_for_status()
            for it in r.json().get('codes', []):
                out[it['code']] = it
        except Exception as e:
            print(f'  ⚠️ 第 {i // batch + 1} 批失败: {str(e)[:80]}')
        if i + batch < len(codes):
            time.sleep(0.5)
    return out


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description='用本地数据服务补齐市值与板块')
    parser.add_argument('--out', default='data.json')
    args = parser.parse_args()

    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), args.out)
    with open(path, encoding='utf-8') as f:
        data = json.load(f)

    results = data.get('results', [])
    codes = [r['code'] for r in results]
    print(f'待补齐 {len(codes)} 只（市值/行业/概念）...')
    t0 = time.time()
    info = enrich(codes)
    print(f'本地服务返回 {len(info)} 只，耗时 {time.time() - t0:.0f}s')

    filled_cap = filled_sector = filled_concept = 0
    kept = []
    for r in results:
        it = info.get(r['code'])
        if not it:
            kept.append(r)
            continue
        cap = it.get('mktcap') or 0
        # 后端过滤：只保留 50亿～300亿
        if not (MIN_CAP <= cap <= MAX_CAP):
            continue
        if cap:
            r['mktcap'] = round(float(cap), 2)
            filled_cap += 1
        industry = it.get('industry') or ''
        if industry:
            r['sector'] = industry          # 行业板块写入 sector（前端板块列）
            filled_sector += 1
        if it.get('region'):
            r['region'] = it['region']       # 地区板块
        concepts = it.get('concepts') or []
        if concepts:
            r['concepts'] = concepts         # 概念板块
            filled_concept += 1
        kept.append(r)

    data['results'] = kept
    data['generated_at'] = time.strftime('%Y-%m-%d %H:%M:%S')
    data['local_enriched'] = True
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f'✅ 完成：市值补齐 {filled_cap} | 行业板块 {filled_sector} | 概念板块 {filled_concept}')
    print(f'   过滤 50亿~300亿 后剩余 {len(kept)} 只 -> {args.out}')


if __name__ == '__main__':
    main()
