# QFQ 前复权增量自动导入管线

## 架构

```
Coze 日历任务 (03:00-05:00)
  → 拉取全量前复权日K → 上传项目空间 /data/qfq/
  → kline_{YYYYMMDD}.csv.gz + signal_{YYYYMMDD}.json

Hermes crontab (05:30, 周一至周五, no_agent)
  → qfq_import.sh 下载信号 → 解析 status
  → ok/partial: 下载数据 → INSERT OR REPLACE → 验证
  → failed/skipped: 静默退出
```

## 文件位置

| 文件 | 路径 |
|------|------|
| 导入脚本 | `~/.hermes/scripts/qfq_import.sh` |
| crontab 条目 | `30 5 * * 1-5` (系统 crontab) |
| 日志 | `~/.logs/qfq_import.log` |
| 晨报集成 | `daily_morning_report.sh` → 📊 数据同步状态 |

## 信号文件格式

Coze 输出到 `/data/qfq/signal_{YYYYMMDD}.json`：

```json
{
  "status": "ok|partial|failed|skipped",
  "trade_date": "2026-06-26",
  "row_count": 5510,
  "finished_at": "2026-06-27T03:45:00+08:00"
}
```

## 关键设计决策

| 决策 | 理由 |
|------|------|
| no_agent=true | 纯 ETL，不需要 LLM |
| deliver=local | 不推微信，避免 iLink 限流 |
| INSERT OR REPLACE | 幂等，重复跑安全 |
| 交易日由 Coze 判定 | Coze 已跳过周末，节假日产 failed/skipped |
| 不用 Tushare | 用户偏好问财，砍掉 Tushare 依赖 |
| 信号文件也下载 | Coze 统一走项目空间，不依赖共享目录 |

## 下载命令

```bash
# 信号文件
coze agent file download --project-id 7652507431196688676 \
  --project-file-path /data/qfq/signal_{YYYYMMDD}.json

# 数据文件
coze agent file download --project-id 7652507431196688676 \
  --project-file-path /data/qfq/qfq_incremental_{YYYYMMDD}.csv.gz
```

## CSV 字段映射

| CSV (Coze) | DB (daily_kline) |
|-----------|-----------------|
| InnerCode | stock_code |
| TradingDay (YYYYMMDD) | date (YYYY-MM-DD) |
| OpenPrice | open |
| HighPrice | high |
| LowPrice | low |
| ClosePrice | close |
| TurnoverVolume | volume |
| TurnoverValue | amount |

## 错误处理

- 信号文件不存在 → `exit 0`（Coze 尚未推送）
- 信号 status=failed → `exit 0`（跳过）
- 网络下载失败 → 3 次重试（指数退避）
- DB 写入失败 → 3 次重试
- 临时文件 → `trap EXIT` 清理
