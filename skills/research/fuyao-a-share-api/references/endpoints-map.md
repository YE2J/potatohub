# Fuyao API 端点地图（2026-09-08 同步，来源：远程 llms.txt）

> 完整参数/字段/示例见本地镜像 `~/my_quant_system/financial-api/toolkit/fuyao/docs/llms-full.txt`（与 https://fuyao.aicubes.cn/llms-full.txt 同版 sha256: de404f22…）

## 能力统计

- REST 参考页：**34** 个 | MCP 工具：**58** 个 | 数据域：行情/财报/指数/基金/特色/估值/竞价/元信息
- 2026-09-08 更新相对旧版(Jul 4)：新增 基金系(≈30 端点)、集合竞价、估值快照、炸板池、跌停池、龙虎榜独立页、个股异动独立页

## REST 域（前缀）→ 主要端点

### A股/行情
| 文档页 | REST 端点 |
|---|---|
| prices | `/api/a-share/prices/snapshot` / `historical` |
| market-dumps | `/api/dump/market-dumps`（全A 10年日K/近10日/复权因子 Parquet） |
| corporate-actions | `/api/a-share/corporate-actions/adjustment-factors` |
| financials | `/api/a-share/financials/{income-statements,balance-sheets,cash-flow-statements}` |
| financial-indicators | `/api/a-share/financials/indicators` |
| calendar | `/api/a-share/calendar/trading-days` |
| auction | `/api/a-share/auction/{snapshot,short-term-benchmark}` |
| valuations | `/api/a-share/valuations/snapshot` |
| limit-up-data | `/api/a-share/special-data/limit-up-*`（涨停/连板天梯/炸板/跌停池） |
| anomaly-analysis | `/api/a-share/special-data/anomaly-analysis-{list,stock}` |
| hot-list-data | `/api/a-share/special-data/{skyrocket,hot-stock}-list[-history/-rank-trend]` |
| dragon-tiger-data | `/api/a-share/special-data/dragon-tiger-list` |

### 指数
| 文档页 | REST 端点 |
|---|---|
| a-share-index | `/api/a-share-index/catalog/ths-index-list` / `constituents/ths-stock-list` / `prices/{snapshot,historical}` |
| index-overview | `/api/a-share-index/overview`（指数概况） |

### 基金（新增整族 ≈30 端点）
| 文档页 | 代表端点 |
|---|---|
| fund-profile | `/api/fund/profile/detail` |
| fund-market | `/api/fund/market/{snapshot,historical}` |
| fund-portfolio | `/api/fund/portfolio/{holdings,asset-allocation,industry-allocation,stock-history,stock-report-dates,bond-history,bond-report-dates}` |
| fund-performance | `/api/fund/performance/{nav,returns,drawdowns,indicators-historical}` |
| fund-managers | `/api/fund/managers/{detail,experience,investment-style,performance}` |
| fund-holders | `/api/fund/holders/{detail,top}` |
| fund-financials | `/api/fund/financials/{income-statements,balance-sheets,indicators}` |
| fund-company | `/api/fund/companies/detail` |
| fund-diagnostics | `/api/fund/diagnostics/detail` |
| fund-news | `/api/fund/news/article-list` |
| fund-offerings | `/api/fund/offerings/list` |
| fund-corporate-actions | `/api/fund/corporate-actions/dividends` |

### 元信息
| 文档页 | REST 端点 |
|---|---|
| ticker-search | `/api/meta/tickers/search` |
| ticker-list | `/api/meta/tickers/list` |

## MCP 工具（58 个，与 REST 同语义）

CLI 客户端（`fuyao.py`/`fuyao_client.py`）已覆盖 A股/指数/特色/元信息约 23 个旧能力；**基金/集合竞价/估值/炸板/跌停 未入客户端**（如需可扩展 fuyao_client 或直接 REST）。工具名列表见远程 `llms.txt`「## MCP 工具」段（59 行）或 llms-full.txt。

## 旧版过时说明

- 旧 README 宣称 "23 REST / 22 MCP"（2026-07-04 镜像）→ 已过期。以本文件 + llms-full.txt 为准。
- fuyao.py CLI 子命令与 fuyao_client.py 函数仅覆盖旧 23 能力子集，新端点需扩展客户端或直连 REST。
