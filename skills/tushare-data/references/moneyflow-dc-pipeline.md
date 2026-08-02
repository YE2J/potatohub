# Tushare moneyflow_dc 增量数据管道参考

## 接口特征

- **接口名**: `moneyflow_dc`
- **数据源**: 东方财富
- **最低积分**: 5000
- **数据范围**: 2023-09-11 至今
- **更新时间**: 每日盘后（15:00~17:00）
- **单次返回**: 全市场 ~6,000 只股票，**1 次 API 调用足够**

## 字段映射（→ moneyflow_daily 表）

| Tushare字段 | 含义 | DB字段 | 单位转换 |
|------------|------|--------|---------|
| `ts_code` | 股票代码 → 去掉.SZ/.SH后缀 | `stock_code` | — |
| `trade_date` | YYYYMMDD → YYYY-MM-DD | `date` | — |
| `net_amount` | 主力净额（超大单+大单） | `main_net_amt`, `net_mf_amt` | ×10000 |
| `buy_elg_amount` | 超大单净额 | `elg_net_amt` | ×10000 |
| `buy_lg_amount` | 大单净额 | `lg_net_amt` | ×10000 |
| `buy_md_amount` | 中单净额 | `md_net_amt` | ×10000 |
| `buy_sm_amount` | 小单净额 | `sm_net_amt` | ×10000 |
| `pct_change`/`close` + rate字段 | 存入 | `raw_json` | JSON序列化 |

**⚠️ 关键陷阱**: `buy_*` 字段名虽含"buy"，但实际是**净额**（正=净流入，负=净流出），不是买入金额。不能映射到 `*_buy_amt` / `*_sell_amt` 列。所有 `*_vol` 列留 NULL。

## 数据源口径差异

同花顺 vs 东方财富对"大单/小单"的划分阈值不同：
- 同花顺：≥10万股或≥50万元为大单；≥100万股或≥500万为特大单
- 东方财富（DC）：阈值略有不同，可能导致同一只股票同一天数据差异极大

**实际案例**（华工科技 2026-06-30）：
- ths_snapshot（同花顺）：总净流入 **+17亿**
- tushare_dc（东方财富）：主力净额 **-3.7亿**

这不是bug，是口径差异。查询时需说明数据来源。

## 增量更新机制

```python
# 核心流程
pro = ts.pro_api()
df = pro.moneyflow_dc(trade_date="20260701")  # 全市场一次返回

# 防重跑
SELECT COUNT(*) FROM moneyflow_daily 
WHERE date='2026-07-01' AND data_source='tushare_dc'  -- 阈值≥100

# 写入
INSERT OR REPLACE INTO moneyflow_daily 
(stock_code, date, main_net_amt, net_mf_amt, elg_net_amt, lg_net_amt, md_net_amt, sm_net_amt, data_source, raw_json)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'tushare_dc', ?)
```

## Hermes Cron 配置

```bash
# no_agent模式：脚本stdout即消息
# 工作日18:45运行，deliver=local（只存不推送）
hermes cron create \
  --name "资金流向-Tushare-DC增量" \
  --schedule "45 18 * * 1-5" \
  --script daily_moneyflow_tushare_dc.sh \
  --no-agent \
  --deliver local
```
