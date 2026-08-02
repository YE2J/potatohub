# Financial-API 数据源集成评估

**评估对象**: 同花顺金融数据 API (fuyao.aicubes.cn) — 商业 API 服务
**评估日期**: 2026-07-04
**访问方式**: REST API + CLI (`toolkit/fuyao/scripts/fuyao.py`) + 本地 MarketDB (DuckDB)

> 这是"API/商业数据源评估"方法论的真实案例。完整集成方案见 `~/my_quant_system/docs/financial-api-integration.md`。

---

## 能力映射

### API 端点 → 现有 DB 覆盖矩阵

| CLI 命令 | 现有表 | 关系 | 优先级 |
|---------|--------|------|--------|
| `tickers-search/list` | stock_basic | 冗余 | 备源 |
| `prices-snapshot` | — | 实时快照，不持久化 | 实时查询 |
| `prices-historical` | daily_kline | 冗余 | 🟢 备源 |
| `corp-actions` | adj_factors | 冗余 | 🟢 备源 |
| `financials-income/balance/cashflow` | A股营业总收入等 | 部分重叠 | 🟡 扩充 |
| `financials-indicators` | —(fina_indicator有限) | 优于现有 | 🟡 替换 |
| `calendar-trading-days` | trade_cal | 冗余 | 🟢 备源 |
| `index-catalog/constituents` | — | **独有** | 可选 |
| `index-snapshot` | — | 实时 | 实时查询 |
| `index-historical` | index_daily | 冗余 | 🟢 备源 |
| **`limit-up-pool`** | ❌ 无对应 | **🔴 独有** | 高优 |
| **`limit-up-ladder`** | ❌ 无对应 | **🔴 独有** | 高优 |
| **`anomaly-analysis-list/stock`** | ❌ 无对应 | **🔴 独有** | 高优 |
| **`skyrocket-list`** | ❌ 无对应 | 🟡 独有 | 中优 |
| **`hot-stock-list/历史/趋势`** | ❌ 无对应 | 🟡 独有 | 中优 |
| **`dragon-tiger-list`** | ❌ 无对应 | 🟡 独有 | 中优 |

### 关键发现

**Financial-API 的核心价值不在于替代，而在于补缺**:
- 5 项**独家数据**（涨停池/连板天梯/异动/热榜/龙虎榜）是 Tushare 完全没有的
- 财务指标接口比 Tushare 更灵活（无 100 条/次限制）
- K线/指数/复权事件作为 Tushare 的**备源**

---

## 集成方案摘要

### 新表设计（5张）

| 表名 | 主键 | 数据来源 | 更新策略 |
|------|------|---------|---------|
| `limit_up_pool` | (trade_date, thscode) | `limit-up-pool` CLI | 增量 16:00 |
| `limit_up_ladder` | (trade_date, board_nums) | `limit-up-ladder` CLI | 全量 16:00 |
| `daily_anomaly` | (trade_date, thscode) | `anomaly-analysis-list` CLI | 增量 15:30 |
| `dragon_tiger_daily` | (trade_date, thscode) | `dragon-tiger-list` CLI | 增量 17:00 |
| `hot_stock_daily` | (trade_date, thscode, rank_type) | `hot-stock-list` CLI | 全量 22:00 |

### 分工边界

| Tushare 保持不动 | Financial-API 新增 |
|-----------------|-------------------|
| daily_kline (primary) | limit_up_pool ★ |
| index_daily (primary) | limit_up_ladder ★ |
| moneyflow_daily (primary) | daily_anomaly ★ |
| daily_factors | dragon_tiger_daily ★ |
| adj_factors (primary) | hot_stock_daily ★ |
| | financial_indicators (可选) |

---

## 环境注意事项

- **Python 版本**：fuyao.py 依赖 Python 3.11+ + requests/typer
- **Hermes venv 不兼容**：Hermes 自带的 urllib3 版本有 `TypeError: unsupported operand type(s) for |: 'type' and 'type'` 问题
- **修复**：使用用户的 pyenv Python `~/.pyenv/versions/3.11.11/bin/python3`
- **环境变量**：`FUYAO_TOKEN` 或 `API_KEY`，在 `.env` 中配置
