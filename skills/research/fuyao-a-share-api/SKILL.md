---
name: fuyao-a-share-api
description: "Use when 查 A股/指数/基金行情、K线、财报、涨跌停、龙虎榜等 fuyao 数据。封装鉴权/CLI/路由。"
---

# Fuyao A股/基金金融数据 API（同花顺官方）

远程数据源：**https://fuyao.aicubes.cn**（Base URL）——同花顺官方结构化金融数据服务，REST + MCP 双形态，数据语义一致。本地客户端与完整契约见 `~/my_quant_system/financial-api/toolkit/fuyao/`。

> 权威契约 = 本地镜像 `~/my_quant_system/financial-api/toolkit/fuyao/docs/llms-full.txt`（2026-09-08 已同步最新版，276KB）或在线 https://fuyao.aicubes.cn/llms-full.txt。字段级细节一律查该文件，不凭记忆猜。

## 何时用 / 何时不用

| 用（实时/新鲜/官方结构化） | 不用（走其他源） |
|---|---|
| A股/指数/基金行情快照与历史K线 | 历史长周期本地批量数据 → `marketdb`/本地 stock_data.db |
| 财报三表、财务指标、交易日历、除复权事件 | 板块资金流口径 → Tushare moneyflow_* |
| 涨跌停池/连板天梯/炸板/跌停、热榜、龙虎榜、个股异动、集合竞价、估值快照 | 研报/新闻/公告原文 → 其他专用源 |
| 基金资料/持仓/业绩/经理/净值 | 宏观经济/海外行情 |
| 标的检索与列表（A股/指数/基金代码表） | — |

## 鉴权（每次调用前）

- API Key：`~/.hermes/.env.fuyao` 中 `FUYAO_TOKEN`（签发于 https://fuyao.aicubes.cn/admin）。**永不写进 prompt/代码/git**。
- REST 请求头：`X-api-key: <token>`（**不是** Bearer——Bearer 会报 `code=2003 Missing X-api-key`）。
- 客户端读取：`fuyao_client.py` 读 env `FUYAO_TOKEN` 或 `API_KEY`。
- 错误码：`2001` 缺失/无效 key；`2003` 无权限；HTTP 429 / `4001` 限流。

## 限流纪律（实测 2026-09-08）

- 短时限流返回 HTTP 429 `{"code":429,"request limit exceeded"}`；业务级限流 `code=4001`。
- 客户端 `fuyao_client._get` 内置指数退避重试（≤3 次，base 1s），cron 调用可自愈。
- 手动连续 curl 可能持续 429 → 遇 429 **降低频率/稍后重试**，勿立即连环重试。

## 调用路径（三选一）

```bash
# 1) REST curl（临时取数）
curl 'https://fuyao.aicubes.cn/api/a-share/prices/snapshot?thscodes=600519.SH' \
  -H "X-api-key: $FUYAO_TOKEN"

# 2) fuyao CLI（项目内，JSON 输出，自动处理重试/校验）
cd ~/my_quant_system && ~/.hermes/venv_cron/bin/python3 \
  financial-api/toolkit/fuyao/scripts/fuyao.py prices-snapshot --thscodes 600519.SH

# 3) fuyao_client Python 函数（typed）
```

常见 CLI 子命令：`tickers-search` `tickers-list` `prices-snapshot` `prices-historical` `corp-actions` `calendar-trading-days` `index-snapshot` `index-historical` `limit-up-pool` `limit-up-ladder` `anomaly-analysis-list/stock` `skyrocket-list` `hot-stock-list[/-history/-rank-trend]` `dragon-tiger-list`（`--help` 看参）。

## 端点全景（2026-09-08 最新：34 REST 参考页 + 58 MCP 工具）

分组概览见 `references/endpoints-map.md`；完整参数/字段/示例 → llms-full.txt。

| 域 | REST 前缀 / 代表端点 | 说明 |
|---|---|---|
| 行情 | `/api/a-share/prices/{snapshot,historical}` | 快照批量/全市场分页；历史K线日/周/月+复权 |
| 全市场导出 | `/api/dump/market-dumps` | 全A 10年日K/近10日K/复权因子 Parquet |
| 财报 | `/api/a-share/financials/{income-statements,balance-sheets,cash-flow-statements,indicators}` | 三表多期序列 + 五类财务指标 |
| 除复权 | `/api/a-share/corporate-actions/adjustment-factors` | 原始分红/送股/配股事件流 |
| 交易日历 | `/api/a-share/calendar/trading-days` | 近一年交易日（ms + yyyyMMdd） |
| 指数 | `/api/a-share-index/{catalog,constituents,prices/snapshot,prices/historical}` | 同花顺指数/板块目录与成分、行情 |
| 集合竞价 | `/api/a-share/auction/{snapshot,short-term-benchmark}` | 竞价快照 + 短线风向标竞价基准 |
| 特色数据 | `/api/a-share/special-data/*` | 涨停/连板/炸板/跌停池、飙升/热股/热股历史/趋势、龙虎榜、个股异动 |
| 估值 | `/api/a-share/valuations/snapshot` | A股估值快照 |
| 基金 | `/api/fund/*`（profile/portfolio/performance/managers/holders/…） | 资料/持仓/业绩/经理/持有人/净值/分红/资讯（~30 端点） |
| 元信息 | `/api/meta/tickers/{search,list}` | 标的消歧检索、代码表分页 |

## 通用约定（防错清单）

- 标的用完整 `thscode`（`600519.SH`），不接受纯 6 位码；基金用 `fund_type`(otc/exchange/reits) + `thscode`（如 `025480.OF`）。
- 时间戳 = 毫秒 Unix（`Asia/Shanghai`）；字段 snake_case + 显式 `currency`。
- 响应统一 `ApiResponse` 信封：业务数据在 `data.item[]`，业务错误经 HTTP200 的 `code` 分发。
- 历史窗口 ≤10 年，超限客户端自动分片。
- 未知标的名/代码 → **先 `tickers-search` 消歧**，勿猜后缀。

## 陷阱（实测）

- 429 后立即重试可能连续失败 → 退避或稍候。
- 旧版 README/docs 曾滞后（2026-09-08 前本地镜像停留在 Jul 4 的 23 REST/22 MCP，缺基金/竞价/估值/炸板/跌停）→ 若字段/端点 404，先确认本地 llms-full.txt 是否最新（对比在线 sha256）。

## 相关

- 完整端点地图：`references/endpoints-map.md`
- 完整契约镜像：`~/my_quant_system/financial-api/toolkit/fuyao/docs/llms-full.txt`
- 项目入口：`~/my_quant_system/financial-api/toolkit/fuyao/README.md`；MCP 配置：`docs/mcp-config.md`
