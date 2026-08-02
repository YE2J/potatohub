# market_moneyflow / hsgt_moneyflow Cron Gap Audit

> 发现于 2026-07-09 P2方案评审 — MiniMax M3 审计发现

## 问题

**`market_moneyflow` 和 `hsgt_moneyflow` 两个表的刷新路径完全不存在。** 数据停滞在 2026-07-03。

| 表 | 最后数据 | 停滞天数 | cron? |
|:---|:--------:|:--------:|:----:|
| `market_moneyflow` | 2026-07-03 | 6+ | ❌ 无 |
| `hsgt_moneyflow` | 2026-07-03 | 6+ | ❌ 无 |

## 为什么致命

P2 大盘温度引擎的 `capital_flow_score`（权重35%）依赖这两个表。如果都停滞：
- 温度引擎只能计算旧日期的温度
- 降级后 `capital_flow_score` 打中性分50
- 温度输出失去实时意义

## 根因

现有cron管线：

| 时间 | 写什么表 | 来源 |
|:----:|:---------|:----|
| 18:00 | `daily_kline` | Tushare |
| 18:15 | `index_daily` | Tushare |
| 18:30 | **`moneyflow_daily`** (个股) | Tushare DC |
| 18:45 | **`sector_moneyflow_ths`** (板块) | Tushare THS |

没有任何 cron 写 `market_moneyflow` 或 `hsgt_moneyflow`。

## Tushare API 接口

| 表 | API | 参数 |
|:---|:----|:----|
| `market_moneyflow` | `pro.moneyflow_mkt_dc(trade_date=date)` | `trade_date`(YYYYMMDD) |
| `hsgt_moneyflow` | `pro.moneyflow_hsgt(trade_date=date)` | `trade_date`(YYYYMMDD) |

## 检测

```sql
SELECT MAX(trade_date) FROM market_moneyflow;
SELECT MAX(trade_date) FROM hsgt_moneyflow;
```

两者均应等于或邻近最新交易日。若差距 > 2 个交易日，则数据链路断裂。
