# QFQ 前复权增量导入管线 v1.1

> 2026-06-27 实施完成。Coze 侧 CodeAct 脚本 + Hermes 侧 cron 导入，全自动增量同步。

---

## 架构

```
Coze 日历任务 (每日 03:00-05:00)
    → 拉取前一日全量前复权日K（腾讯 fqkline，~5,500 只）
    → 上传到项目空间 /data/qfq/:
        qfq_incremental_{YYYYMMDD}.csv.gz   （数据）
        signal_{YYYYMMDD}.json              （信号）
    → Coze 内置周末跳过；节假日产 status=partial/failed

Hermes cron (05:30, 周一至周五, no_agent, deliver=local)
    → 下载信号文件 → 解析 status
    → 下载数据文件 → 解压 → INSERT OR REPLACE
    → 验证 → 写日志
```

## 数据表

- **数据库**: `/Users/yellow/my_quant_system/stock_data.db`
- **目标表**: `daily_kline` (stock_code, date, open, high, low, close, volume, amount, amplitude, pct_change, change, turnover)
- **stock_code**: 恒生聚源 InnerCode（非股票代码）

## 信号文件格式

```json
{
  "status": "ok | partial | failed | skipped",
  "trade_date": "YYYY-MM-DD",
  "row_count": 5510,
  "finished_at": "ISO8601",
  "coze_project_path": "/data/qfq/qfq_incremental_XXX.csv.gz"
}
```

## Hermes 侧组件

| 组件 | 路径 |
|------|------|
| 导入脚本 | `~/.hermes/scripts/qfq_import.sh` |
| cron 调度 | 系统 crontab: `30 5 * * 1-5` |
| 数据日志 | `~/.logs/qfq_import.log` |
| 晨报集成 | `~/.hermes/scripts/daily_morning_report.sh` § 📊 数据同步状态 |

## 设计决策

| 决策 | 理由 |
|------|------|
| 不用 Tushare trade_cal | Coze 信号 + 周末跳过已足够；节假日产 partial/failed 由 status 处理 |
| 不用共享目录直写 | Coze 现走项目空间，统一用 `coze agent file download` |
| no_agent + deliver=local | 纯 ETL 不需 LLM；不推微信避免 iLink 限流 |
| INSERT OR REPLACE | 幂等，重复跑安全 |
| 3 次指数退避重试 | 网络/DB 瞬断覆盖 |
| trap EXIT 清理 | 临时文件不残留 |

## CSV → DB 映射

| CSV 字段 | DB 字段 | 转换 |
|----------|---------|------|
| InnerCode | stock_code | 直传 |
| TradingDay | date | YYYYMMDD → YYYY-MM-DD |
| OpenPrice | open | float |
| HighPrice | high | float |
| LowPrice | low | float |
| ClosePrice | close | float |
| TurnoverVolume | volume | float |
| TurnoverValue | amount | float |
| — | amplitude/pct_change/change/turnover | NULL |

## 晨报数据同步检查

在 `daily_morning_report.sh` §7 中实现：

- 读取 `~/.logs/qfq_import.log` 最近 3 行
- 查询 `SELECT MAX(date) FROM daily_kline`，计算滞后天数
- 滞后 ≤0 → ✅ 正常，1 天 → ⚠️ 注意，≥2 天 → 🔴 告警
