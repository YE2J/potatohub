# 与 daily_stock_analysis 的关系

## 定位

两套系统**保持独立，不合并**，通过数据单向同步协作：

| | my_quant_system | daily_stock_analysis |
|---|---|---|
| 功能 | 量化回测引擎 | AI日报分析系统 |
| 数据 | SQLite 53MB/307股 | 自建 DB 976KB/4股 |
| 工作流 | 数据→TDX指标→策略→回测 | 数据→LLM分析→推送 |

## 桥接方案：SQLiteFetcher

已为 daily_stock_analysis 创建自定义数据源 `SQLiteFetcher`，让它直接从 my_quant_system 的 `stock_data.db` 读取行情数据。

**文件位置**：
- `/Users/yellow/daily_stock_analysis/data_provider/sqlite_fetcher.py`

**注册**：在 `data_provider/base.py` 和 `__init__.py` 中作为最高优先级（priority=-1）。

**效果**：daily_stock_analysis 拉行情时优先走本地数据库（307股/44K行），失败才回退网络源。

**配置零修改**：fetcher 硬编码路径 `~/my_quant_system/stock_data.db`，无需 `.env` 配置。

## 数据流向

```
my_quant_system/stock_data.db  ← cron 每天拉
        │
        │ (SQLiteFetcher 只读)
        ▼
daily_stock_analysis/          ← 按需 LLM 分析
```
