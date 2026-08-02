# A-Share Database Table Catalog (stock_data.db)

Reference for the A-share data pipeline tables tracked by the wiki.
Discovered during the 2026-07-12 valuation correction session.

## K线 (Price)

| Table | Date Column | Date Format | Notes |
|-------|-------------|-------------|-------|
| `daily_kline` | `date` | `YYYY-MM-DD` | Primary. also has legacy YYYYMMDD rows (~147, watchlist only) |
| `daily_factors` | `trade_date` | `YYYY-MM-DD` | Factor data on same stocks. |

## 资金流 (Fund Flow)

| Table | Date Column | Date Format | Notes |
|-------|-------------|-------------|-------|
| `moneyflow_daily` | `date` | `YYYY-MM-DD` | Primary. `net_mf_amt` = net flow. |
| `sector_moneyflow_dc` | `trade_date` | **`YYYYMMDD`** ⚠️ | DC sector-level (different from moneyflow_daily.date format!) |
| `industry_moneyflow_dc` | `trade_date` | `YYYYMMDD` | DC industry-level |
| `hsgt_moneyflow` | `trade_date` | `YYYYMMDD` | 北向/南向. |
| `industry_moneyflow_ths` | `trade_date` | `YYYYMMDD` | THS industry level. |
| `sector_moneyflow_ths` | `trade_date` | `YYYYMMDD` | THS sector level. |
| `market_moneyflow` | `trade_date` | `YYYYMMDD` | Market aggregate. |

## 估值 (Valuation) — ⚠️ CRITICAL: Two tables

| Table | Date Column | Date Format | Status | Notes |
|-------|-------------|-------------|--------|-------|
| `valuation_results` | `run_id` (int) / `run_date` | `YYYY-MM-DD HH:MM:SS` | ✅ ACTIVE | v3.2 PE-Band model. Use `MAX(run_id)`, NOT `MAX(run_date)`. |
| `valuation_daily_signal` | `trade_date` | `TEXT` | ❌ EMPTY | v1 old model. **Do not track this table.** |

**valuation_results key columns:**
- `run_id` (INTEGER) — batch identifier, use `MAX(run_id)` for latest
- `data_as_of` (DATE) — data cutoff date (for staleness tracking)
- `run_date` (DATETIME) — when batch ran
- `safety_margin` (REAL) — decimal, ×100 for %. Positive=undervalued
- `rating` (TEXT) — 显著低估/低估/偏低/中性/偏高/高估/显著高估
- `primary_model` / `model_version` — model tracking

## 指数 (Index)

| Table | Date Column | Date Format | Notes |
|-------|-------------|-------------|-------|
| `index_daily` | `trade_date` | `YYYY-MM-DD` | Major indexes (上证, 科创50, etc.) |

## 涨停异动 (Limit-up / Anomalies)

| Table | Date Column | Date Format | Notes |
|-------|-------------|-------------|-------|
| `dragon_tiger_daily` | `trade_date` | `YYYY-MM-DD` | 龙虎榜 |
| `daily_anomaly` | `trade_date` | `YYYY-MM-DD` | 个股异动 |

## 辅助表 (Helper)

| Table | Columns | Purpose |
|-------|---------|---------|
| `stock_name_map` | stock_code (PK), stock_name, source | Name lookup for any stock code. Simpler than daily_kline join. |
| `cron_push_log` | id, job_name, job_id, status, finished_time, content_path, duration_ms, log_tail | Cron execution history. Query `ORDER BY id DESC` for latest. |
| `market_temperature` | trade_date, temperature_score, trend_direction, position_ratio, limit_up_count, limit_down_count | 大盘温度 (0-100). trend_direction = 'up'/'down'/'stable'. |

## Verification Query Template (Updated)

```sql
-- Quick health check for all tracked tables
SELECT 'daily_kline' as tbl, MAX(date) as latest, COUNT(*) as cnt FROM daily_kline
UNION ALL
SELECT 'daily_factors', MAX(trade_date), COUNT(*) FROM daily_factors
UNION ALL
SELECT 'moneyflow_daily', MAX(date), COUNT(*) FROM moneyflow_daily
UNION ALL
SELECT 'valuation_results', MAX(data_as_of), COUNT(*) FROM valuation_results
UNION ALL
SELECT 'index_daily', MAX(trade_date), COUNT(*) FROM index_daily
UNION ALL
SELECT 'dragon_tiger_daily', MAX(trade_date), COUNT(*) FROM dragon_tiger_daily
UNION ALL
SELECT 'stock_name_map', null, COUNT(*) FROM stock_name_map
ORDER BY tbl;
```

## Historical Correction

- Prior to 2026-07-12, the wiki tracked `valuation_daily_signal` (empty) and
  reported "valuation stagnant 24 days." Actual data was in `valuation_results`
  with latest run 2026-07-11.
- 6 consecutive wiki updates (07-05 through 07-11) compounded this error.
- All affected pages were corrected on 2026-07-12 with timestamped corrections.
