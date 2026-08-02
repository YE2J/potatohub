# 资金流数据管线（2026-06-29 已切换）

> 🗑️ **此管线已停用**。东方财富 push2his 不再作为资金流主数据源。
> 当前主数据源为同花顺 THS 全量数据（14M 行, 5,663 只, data_source='ths'）。
> 详见 `references/ths-moneyflow-import.md`。

## 历史记录

**曾使用的数据源**：

| 阶段 | 数据源 | 时间 |
|------|--------|------|
| 1. 东方财富 push2his | 每日 18:30 cron，100 只自选股，~830 行 | 2026-06-04 ~ 2026-06-28 |
| 2. 问财 OpenAPI hithink-market-query | 双 Key 回补，148 只，04:00 cron | 2026-06-27（一天） |
| **3. 同花顺 THS（当前）** | **5,663 只全量，一次性导入** | **2026-06-29 → 今** |

**东方财富 URL 模式**（保留参考）：
```
https://push2his.eastmoney.com/api/qt/stock/fflow/daykline/get
  ?lmt=50&klt=1&secid=0.{code}&fields1=f1,f2,f3,f7
  &fields2=f51,f52,f53,f54,f55,f56,f61,f62&fmt=json
```

## 历史 cron

- `209c43908019` — 每日资金流更新（东方财富），已禁用
- `daily_moneyflow_iwencai.sh backfill` (04:00) — 问财回补，已禁用
- `daily_moneyflow_iwencai.sh incremental` (18:30) — 问财增量，已禁用
