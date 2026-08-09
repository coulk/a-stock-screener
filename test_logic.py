# -*- coding: utf-8 -*-
"""离线验证 analyze_stock 判定逻辑（构造数据，不依赖网络）"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
import screener

def make_kline(prices, lows=None, volumes=None, up_then_pullback=True):
    """构造日K：默认先上涨再回踩（第一次回踩+缩量）"""
    n = len(prices)
    close = np.array(prices, dtype=float)
    if lows is None:
        lows = close * 0.99
    if volumes is None:
        # 上涨放量、回踩缩量
        volumes = np.full(n, 1e6)
        volumes[:n - 3] = 1.2e6
        volumes[-3:] = 0.5e6
    dates = pd.date_range('2026-05-01', periods=n).strftime('%Y-%m-%d')
    return pd.DataFrame({'date': dates, 'open': close * 0.995,
                         'close': close, 'high': close * 1.01,
                         'low': lows, 'volume': volumes})

# ---- 场景1：上涨趋势 + 首次回踩 + 缩量 + 收盘确认（应命中）----
# 前26天从10涨到15（MA20向上，约13.5），随后3天回踩到 MA20 附近并缩量，最后收盘收回 MA20 上方
prices = list(np.linspace(10, 15, 26)) + [13.9, 13.5, 14.1]
df = make_kline(prices)
r = screener.analyze_stock('600001', '测试A', df)
print('场景1(上涨+首次回踩+缩量):', 'PASS 命中' if r else 'FAIL 未命中')
if r:
    print('   ', r)

# ---- 场景2：下跌趋势（MA20向下，应不命中）----
prices = list(np.linspace(15, 10, 35))
df = make_kline(prices, up_then_pullback=False)
r = screener.analyze_stock('600002', '测试B', df)
print('场景2(下跌趋势):', 'PASS 未命中' if r is None else 'FAIL 误命中')

# ---- 场景3：回踩但放量（缩量条件不满足，应不命中）----
prices = list(np.linspace(10, 15, 26)) + [14.6, 14.4, 14.9]
volumes = np.full(29, 2e6)  # 全放量
df = make_kline(prices, volumes=volumes)
r = screener.analyze_stock('600003', '测试C', df)
print('场景3(回踩但放量):', 'PASS 未命中' if r is None else 'FAIL 误命中')

# ---- 场景4：收盘跌破MA20（收盘未确认，应不命中）----
prices = list(np.linspace(10, 15, 26)) + [14.6, 14.4, 13.5]  # 最后收盘大幅跌破
df = make_kline(prices)
r = screener.analyze_stock('600004', '测试D', df)
print('场景4(收盘跌破MA20):', 'PASS 未命中' if r is None else 'FAIL 误命中')

# ---- 场景5：第二次回踩（此前已跌破过MA20，is_first 应为 False）----
# 先涨，中间一次跌破MA20，再涨，再回踩
prices = list(np.linspace(10, 15, 26)) + [14.2, 13.0, 14.0] + [14.8, 15.2, 15.5] + [15.0, 14.8, 15.3]
volumes = np.full(len(prices), 1e6)
volumes[-3:] = 0.4e6  # 末段缩量
df = make_kline(prices, volumes=volumes)
r = screener.analyze_stock('600005', '测试E', df)
if r:
    print('场景5(第二次回踩):', 'PASS is_first=False' if r['is_first'] is False else 'FAIL is_first应为False', r)
else:
    print('场景5(第二次回踩): 未命中（检查构造是否合理）')
