# 统一量化回测系统 — 完整文件清单

> 更新日期：2026-06-16
> 系统路径：`~/my_quant_system/`
> 旧系统（`~/Documents/量化回测/`）已于 2026-06-16 彻底删除

## 核心策略模块（从旧系统迁入，逻辑原封不动）

| 文件 | 行数 | 来源 | 说明 |
|------|------|------|------|
| `indicators_tdx.py` | 796 | 旧系统 `indicators.py` | TDX核心函数 + 3个指标（主力雷达、AI活跃度、GS信号） |
| `strategies_v3.py` | 538 | 旧系统 `strategies.py` | v3 规则引擎，打分制单票 |
| `backtest_v4.py` | ~530 | 旧系统 `backtest_v4.py` | v4 多票组合引擎（导入已适配） |
| `analyze_losers.py` | ~100 | 旧系统 `analyze_losers.py` | 亏损诊断脚本 |

## 桥接与配置

| 文件 | 行数 | 说明 |
|------|------|------|
| `bridge.py` | ~350 | 桥接层：DB→DataFrame→指标→回测→DB保存。CLI + API 统一入口 |
| `config.py` | ~90 | 全局配置，包含 `STOCKS_V4`（99只）、`V4_PARAMS`、`DB_PATH` 等 |

## 数据层

| 文件 | 说明 |
|------|------|
| `data_manager.py` | StockDataManager：SQLite + Parquet 双存储，含 `load_to_dataframe()` |
| `stock_data.db` | SQLite（53MB, 14表, 307只股票） |
| `data/parquet/` | 106个 .parquet 文件（860KB） |
| `.hermes/scripts/daily_update_v2.sh` | Shell wrapper：强制使用 venv Python 执行 daily_update.py（规避 cron 环境 Python 缺少 pandas 问题） |
| `.hermes/scripts/daily_update.py` | cron job 被调脚本（由 wrapper 调用，每夜00:00自动增量更新） |
| `fast_download.py` | 快速批量下载工具 |

## Web 应用

| 文件 | 说明 |
|------|------|
| `app/main.py` | FastAPI（~1100行），含 v4/v3 API 路由 |
| `app/templates/` | 12个 Jinja2 模板 |
| `app/static/style.css` | 样式 |

## 系统二原有模块（保留）

| 文件 | 说明 |
|------|------|
| `indicators.py` | backtrader SMA/EMA/ATR |
| `strategy.py` | backtrader MyStrategy（双均线demo） |
| `main.py` | 系统二原有 CLI 入口 |
| `valuation_channel.py` | 估值通道生成器 |
| `valuation_integration.py` | 估值集成 |
| `run_valuation_subprocess.py` | 估值子进程 |

## Web 配置

| 文件 | 说明 |
|------|------|
| `web_data/watchlist.json` | Web UI 自选股配置 |
| `web_data/strategies/index.json` | 策略索引 |
| `web_data/strategies/双均线金叉死叉.py` | 示例策略 |
| `自选股清单.txt` | 104只自选股文本列表 |

## 报告输出

| 文件 | 说明 |
|------|------|
| `reports/backtest_report_000001.html` | 旧 backtrader 回测报告 |
| `reports/backtest_report_000988.html` | 旧 backtrader 回测报告 |
| `reports/valuation/000988.png` | 估值通道图 |
| `reports/valuation/002409.png` | 估值通道图 |
| `reports/valuation/301338.png` | 估值通道图 |

## 运行方式

```bash
# v4 多票组合回测（4只示例）
cd ~/my_quant_system
.venv/bin/python bridge.py --engine v4 --codes 301338 000988 301526 000999

# v4 全量回测（99只）
.venv/bin/python bridge.py --engine v4

# 同步自选股
.venv/bin/python bridge.py --sync-watchlist

# 启动 Web 应用
cd ~/my_quant_system && .venv/bin/python -m app.main
```
