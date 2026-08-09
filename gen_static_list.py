# -*- coding: utf-8 -*-
"""生成增强版静态列表 stock_list.json：代码+名称+总市值+成交额+涨跌幅（腾讯快照补充）。
用法：python gen_static_list.py   # 本地大陆环境运行，提交仓库供 Actions 使用"""
import json
import time
import requests

UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
      'Referer': 'https://gu.qq.com/'}

def to_symbol(code):
    c = str(code).zfill(6)
    return f"sh{c}" if c.startswith('6') else f"sz{c}"

def main():
    base = json.load(open('stock_list.json', encoding='utf-8'))
    print(f'基础列表 {len(base)} 只')

    # 腾讯批量补充市值/成交额
    batch = 50
    rows = {}
    total = len(base)
    for i in range(0, total, batch):
        chunk = base[i:i + batch]
        syms = ','.join(to_symbol(x['code']) for x in chunk)
        try:
            r = requests.get(f'https://qt.gtimg.cn/q={syms}', headers=UA, timeout=10)
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
                    rows[str(f[2]).zfill(6)] = {
                        'mktcap': float(f[45]) * 1e8,     # 亿 -> 元
                        'amount': float(f[37]) * 1e4,     # 万 -> 元
                        'chg_pct': float(f[32]),
                    }
                except (ValueError, IndexError):
                    continue
        except Exception:
            pass
        if (i // batch + 1) % 20 == 0 or i + batch >= total:
            print(f'  进度 {min(i + batch, total)}/{total}，已获取 {len(rows)}')
        time.sleep(0.1)

    out = []
    for x in base:
        c = x['code']
        extra = rows.get(c, {})
        out.append({
            'code': c,
            'name': x['name'],
            'mktcap': extra.get('mktcap', 0),
            'amount': extra.get('amount', 0),
            'chg_pct': extra.get('chg_pct', 0),
        })
    json.dump(out, open('stock_list.json', 'w', encoding='utf-8'), ensure_ascii=False)
    with_data = sum(1 for x in out if x['mktcap'] > 0)
    print(f'完成：{len(out)} 只，含市值数据 {with_data} 只')

if __name__ == '__main__':
    main()
