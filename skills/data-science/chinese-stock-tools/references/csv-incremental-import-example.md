# CSV Incremental Import — Concrete Example

**Session**: 2026-07-16 — imported 大盘资金流向.csv & 港股通每日成交统计.csv into stock_data.db

## Overview

Two external CSV files were incrementally imported into the quant system's SQLite database. One mapped to an existing table (`market_moneyflow`), the other required a new table (`ggt_daily`).

## File 1: 大盘资金流向.csv → market_moneyflow

### Source Structure

| Column | Type | Notes |
|--------|------|-------|
| 交易日期 | YYYYMMDD | 20230417 ~ 20260716 |
| 上证收盘点位 | float | sh_close |
| 上证涨跌幅(%) | float | sh_pct_change |
| 深证收盘点位 | float | sz_close |
| 深证涨跌幅(%) | float | sz_pct_change |
| 主力净流入(元) | float | main_net_inflow |
| 主力净流入占比(%) | float | main_net_inflow_ratio |
| 特大单流入(元) | float | elg_net_inflow |
| 特大单占比(%) | float | elg_net_inflow_ratio |
| 大单流入(元) | float | lg_net_inflow |
| 大单占比(%) | float | lg_net_inflow_ratio |
| 中单流入(元) | float | md_net_inflow |
| 中单占比(%) | float | md_net_inflow_ratio |
| 小单流入(元) | float | sm_net_inflow |
| 小单占比(%) | float | sm_net_inflow_ratio |

### Incremental Logic

- Existing DB: 780 rows (2023-04-17 ~ 20260710)
- CSV: 787 rows (20230417 ~ 20260716)
- Missing: **7 rows** (20260706, 20260707, 20260708, 20260713, 20260714, 20260715, 20260716)
- All fields 1:1 mapped, no transformation needed

## File 2: 港股通每日成交统计.csv → ggt_daily (New Table)

### Why Not hsgt_moneyflow?

The existing `hsgt_moneyflow` table stores **cumulative north/south totals** (南北向资金累计值), while the CSV has **daily buy/sell transaction data** (日频买入/卖出明细). Different data type → needs its own table.

### Source Structure

| Column | Type | DB Column |
|--------|------|-----------|
| 交易日期 | YYYYMMDD | trade_date |
| 买入成交金额(亿元) | float | buy_amount |
| 买入成交笔数(万笔) | float | buy_volume |
| 卖出成交金额(亿元) | float | sell_amount |
| 卖出成交笔数(万笔) | float | sell_volume |

### Import Details

- Full history: 2014-11-17 ~ 20260715 (2,659 rows)
- All rows were new (table was empty)

## Key Pitfall Avoided: Date Format

The existing `market_moneyflow` table uses **YYYYMMDD** (no dashes, e.g. `20260710`). The initial INSERT converted CSV dates to `YYYY-MM-DD` format, creating dual-format entries that break `MAX()` queries.

**Fix**: `UPDATE market_moneyflow SET trade_date = REPLACE(trade_date, '-', '') WHERE trade_date LIKE '%-%';`

## Verification Query

```sql
SELECT 'market_moneyflow' as tbl, COUNT(*) as rows, MIN(trade_date) as min_d, MAX(trade_date) as max_d FROM market_moneyflow
UNION ALL
SELECT 'ggt_daily', COUNT(*), MIN(trade_date), MAX(trade_date) FROM ggt_daily;
```
