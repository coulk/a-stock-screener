# A股 20日线回踩选股（GitHub Pages 每日自动更新）

基于 20 日线回踩体系，扫描**全市场沪深主板**，每日收盘后自动筛选并更新网页。

## 筛选体系（当前会话确认）

| 要点 | 规则 |
|:---|:---|
| 趋势 | MA20 向上或近 5 日刚拐头（含上涨转折），收盘价在 MA20 上方 |
| 回踩 | 近 3 日内最低价触及 MA20 附近（上方 0~5% 内） |
| 第一次回踩最值钱 | 自 MA20 拐点以来无更早收盘跌破/贴近 MA20 → 标记「首次」并优先 |
| 必须缩量 | 回踩日成交量 < 前 5 日均量 × 80% |
| 20日线斜率越大越好 | MA20 近 5 日变化率，作为排序与评分依据 |
| 收盘确认 | 盘中跌破不算数，最后收盘须收回 MA20 上方 |
| 板块共振 | 板块等权指数 MA20 走平/向上 + 板块收盘贴近板块MA20（调整尾声）→ 加分 |

粗筛：沪深主板 + 排除 ST + 成交额 ≥ 2 亿 + 总市值 ≥ 50 亿 + 当日涨跌幅 ±9.8% 内（排除涨跌停）。

## 数据源（多源降级）

- 全市场快照：腾讯 `qt.gtimg.cn` 批量 → 东财 `stock_zh_a_spot_em` → 新浪 `stock_zh_a_spot`
- 个股日K：Yahoo Finance chart API（GitHub Actions 海外可用）→ `quotes.sina.cn` 直连 → 腾讯/新浪/雪球/东财多源降级 → akshare 东财
- 板块映射：东财行业板块 → 新浪板块（失败则板块共振降级为数据不足，不影响主筛选）

## 本地运行

```bash
pip install -r requirements.txt
python screener.py            # 全市场扫描，生成 data.json
python screener.py --candidates 600756,002410,002218   # 测试模式：指定候选
python test_logic.py          # 离线验证判定逻辑（不依赖网络）
```

## 自动更新

`.github/workflows/update.yml` 每个工作日北京时间 15:30 运行：
1. 安装依赖 → 运行 `screener.py` 生成 `data.json`
2. 有变化则提交并推送
3. （GitHub Pages 已配置为从 main 分支部署时，网页自动更新）

## 启用 GitHub Pages

1. 仓库 Settings → Pages
2. **Build and deployment** → Source 选择 **Deploy from a branch**
3. Branch 选择 `main`，路径 `/`（root），Save
4. 等待首次部署，访问 `https://<用户名>.github.io/a-stock-screener/`

或手动触发：Actions → 「每日A股20日线回踩筛选」→ Run workflow。

## 较上一日涨跌幅 / 总市值

- 结果表中 `pct_chg`（今日收盘 vs 昨日收盘涨跌幅 %）与 `prev_close`（昨收），由 `screener.py` 从日K数据计算（quotes.sina.cn/Yahoo，Actions 海外可用）
- 结果表中 `mktcap`（总市值，**单位：亿元**），由全市场快照直接带出：
  - 东财源 `f20`、腾讯源 `f[45]*1e8`、新浪源「总市值」，统一换算为亿元
  - 粗筛 `MIN_MARKET_CAP=5e9`（≥50 亿）一直在用，本次只是把数值透传到结果
- 前端「涨跌幅%」红涨绿跌、「总市值(亿)」默认从大到小，均支持点击列头排序

## 本地 MCP 辅助工具

网页每日自动更新走现有管线（quotes.sina.cn/Yahoo，GitHub Actions 海外可用）。
以下 MCP 作为**本地辅助**（数据源为东财，仅大陆网络可用，Actions 海外不可用）：

| MCP | 用途 | 启动方式 |
|:---|:---|:---|
| `stock-mcp-server`（GitHub: 1018053166） | 实时行情/K线/排行榜/股东分析，15 工具 | `node stock-mcp-server/index.js` |
| `stock-sdk-mcp`（npm, chengzuopeng） | 全市场批量行情/条件选股/板块/技术指标，69 工具 | `npx -y stock-sdk-mcp` |

本地刷新实时涨跌幅与总市值（可选，需大陆网络）：
```bash
python mcp_update.py --market   # 打印三大指数 + 用 stock-mcp-server 刷新 data.json 涨跌幅与总市值
```
`mcp_update.py` 逐只调用 `get_stock_realtime`，顺带刷新 `price` / `pct_chg` / `prev_close` / `mktcap`（总市值亿元）。
注意：vendored 的 `stock-mcp-server/fetcher.js` 已修复 fields 列表缺失 `f116,f117` 的 bug（原版请求未带这两个字段，导致 `totalMarketCap` 恒为 0）。

## 免责声明

本页面结果仅为技术面初筛，不构成任何投资建议。股市有风险，投资需谨慎。
