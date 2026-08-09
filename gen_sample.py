# -*- coding: utf-8 -*-
"""生成样例 data.json（用于本地页面渲染验证，非真实数据）"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
import screener


def make_kline(prices, volumes=None):
    n = len(prices)
    close = np.array(prices, dtype=float)
    if volumes is None:
        volumes = np.full(n, 1e6)
        volumes[:n - 3] = 1.2e6
        volumes[-3:] = 0.5e6
    dates = pd.date_range('2026-05-01', periods=n).strftime('%Y-%m-%d')
    return pd.DataFrame({'date': dates, 'open': close * 0.995, 'close': close,
                         'high': close * 1.01, 'low': close * 0.99, 'volume': volumes})


def gen(name, base):
    prices = list(np.linspace(base, base * 1.5, 26)) + [base * 1.39, base * 1.35, base * 1.41]
    return screener.analyze_stock('600001', name, make_kline(prices))


results = [
    {'code': '600756', 'name': '浪潮软件', 'sector': '电子信息', 'price': 15.56, 'ma20': 15.04,
     'dist_ma20': 3.47, 'slope_ma20': 5.46, 'pullback_date': '2026-08-07', 'vol_ratio': 0.62,
     'is_first': True, 'resonance': False, 'score': 66.9},
    {'code': '002410', 'name': '广联达', 'sector': '电子信息', 'price': 9.39, 'ma20': 8.99,
     'dist_ma20': 4.47, 'slope_ma20': 4.08, 'pullback_date': '2026-08-07', 'vol_ratio': 0.75,
     'is_first': True, 'resonance': False, 'score': 62.0},
    {'code': '002218', 'name': '拓日新能', 'sector': '电子器件', 'price': 4.10, 'ma20': 3.85,
     'dist_ma20': 6.60, 'slope_ma20': 3.36, 'pullback_date': '2026-08-07', 'vol_ratio': 0.59,
     'is_first': True, 'resonance': True, 'score': 76.3},
    {'code': '000058', 'name': '深赛格', 'sector': '电子器件', 'price': 6.67, 'ma20': 6.37,
     'dist_ma20': 4.64, 'slope_ma20': 3.29, 'pullback_date': '2026-08-07', 'vol_ratio': 0.65,
     'is_first': True, 'resonance': True, 'score': 74.9},
    {'code': '600570', 'name': '恒生电子', 'sector': '电子信息', 'price': 22.77, 'ma20': 21.70,
     'dist_ma20': 4.94, 'slope_ma20': 2.62, 'pullback_date': '2026-08-07', 'vol_ratio': 0.77,
     'is_first': True, 'resonance': False, 'score': 57.2},
    {'code': '600602', 'name': '云赛智联', 'sector': '电子器件', 'price': 17.93, 'ma20': 17.93,
     'dist_ma20': 0.01, 'slope_ma20': 2.82, 'pullback_date': '2026-08-07', 'vol_ratio': 0.72,
     'is_first': False, 'resonance': True, 'score': 45.6},
    {'code': '000948', 'name': '南天信息', 'sector': '电子信息', 'price': 14.80, 'ma20': 14.35,
     'dist_ma20': 3.11, 'slope_ma20': 4.65, 'pullback_date': '2026-08-07', 'vol_ratio': 0.63,
     'is_first': False, 'resonance': False, 'score': 37.0},
]

data = {
    'generated_at': '2026-08-09 15:35:00',
    'market': '沪深主板',
    'total_spot': 5539,
    'candidates': 486,
    'kline_ok': 482,
    'matched': len(results),
    'params': {'min_amount': 200000000.0, 'min_market_cap': 5000000000.0,
               'touch_pct': 0.05, 'vol_ratio': 0.8, 'slope_days': 5},
    'sector_resonance': {'电子器件': {'ok': True, 'slope': 1.5, 'dist': 3.93}},
    'results': results,
}
with open('data.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
print('样例 data.json 已生成，%d 只' % len(results))
