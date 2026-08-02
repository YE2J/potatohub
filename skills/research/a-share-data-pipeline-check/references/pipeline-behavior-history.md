# Stock Data Pipeline — Observed Behavior (June–July 2026)

> Historical record of data pipeline behavior across multiple daily wiki cron runs.
> Use this to quickly assess whether current data gaps match known patterns.

## Pipeline Freshness Timeline

### 2026-W26 (06-22 ~ 06-28)

| Date | daily_kline | moneyflow_daily | valuation | Notes |
|------|-------------|-----------------|-----------|-------|
| 06-22 (Mon) | 06-22 | 06-22 (5,193) | 06-17 | Baseline — all pipelines working |
| 06-23 (Tue) | 06-23 | 06-22 (stale) | 06-17 | Moneyflow cron failed |
| 06-24 (Wed) | 06-23 | 06-22 (stale) | 06-17 | ... |
| 06-25 (Thu) | 06-23 | 06-22 (stale) | 06-17 | ... |
| 06-26 (Fri) | 06-26 ✅ | 06-22 (stale) | 06-17 | Kline recovered! Moneyflow still stuck |
| 06-27 (Sat) | 06-26 ✅ | 06-22 (stale, d5) | 06-17 | Weekend |
## Pipeline Freshness Timeline

### 2026-W27 (06-29 ~ 07-05)

| Date | daily_kline | moneyflow_daily | valuation | Notes |
|------|-------------|-----------------|-----------|-------|
| 06-29 (Mon) | **06-29 (10,360)** | **06-29 (11,152) 🚀** | 06-17 | Manual backfill; kline count includes non-standard codes |
| 06-30 (Tue) | **06-30 (10,354)** | **06-30 (11,152) 🚀** | 06-17 | Manual backfill (two runs: one at 00:19, one at 00:32) |
| **07-01 (Wed)** | **0 ❌** | 06-30 (gap d1) | 06-17 | **Cron silently did not trigger** — NOT a holiday. A-share trading day confirmed via Tushare trade_cal. **Backfilled 07-04 08:50 → 5,189 rows** |
| 07-02 (Thu) | **07-02 (5,194) ✅** | **07-02 (5,703) 🚀** | 06-17 | Kline recovered via 18:00 cron; moneyflow sustained |
| 07-03 (Fri) | **07-03 (5,193) ✅** | **07-03 (5,970) 🚀** | 06-17 | Both pipelines healthy. cron_log_helper integer bug false alarm |
| 07-04 (Sat) | 07-03 ✅ | 07-03 ✅ | 06-17 ❌(d17) | Weekend. **trade_cal table created** + weekly sync cron set up |

### Key Timeline Events

- **07-02 00:18**: Manual backfill attempted for 06-30 (token not set → failed, retried → skipped as already present)
- **07-02 00:19~00:32**: Manual backfill for 06-29 → inserted 5,189 standard rows (plus non-standard codes = 10,360 total)
- **07-02 00:32~00:40**: Manual backfill for 06-30 → inserted 5,186 standard rows (plus non-standard = 10,354 total)
  - _Both backfills included non-standard codes (old delisted stocks like `10000`, `10036`, `100636`) because stock_basic returned more entries at that time_
- **07-02 18:00~18:08**: Incremental cron ran for 07-02 → clean 5,194 rows
- **07-03 18:00~18:07**: Incremental cron ran for 07-03 → clean 5,193 rows
- **07-04 08:50~08:55**: Manual backfill for 07-01 → 5,189 rows (missed by silent cron failure)
- **07-04 09:00**: Created `trade_cal` table in stock_data.db from Tushare API (25,768 rows, SSE+SZSE, 1990-12~present). Set up weekly refresh cron (Mon 10:00)
- **07-04**: Updated `qfq_tushare_daily.py` — `get_latest_trade_date()` now queries local `trade_cal` table first, falls back to Tushare API

## Key Patterns

### Data Count Variation

| Coverage Level | Count | When | Source |
|---------------|-------|------|--------|
| Normal (standard only) | ~5,100–5,200 | Regular incremental runs | `qfq_tushare_daily.py` with GLOB filter |
| Broad (incl. non-standard) | ~10,300–11,100 | Manual backfill, historical recovery | `stock_basic` with broader scope |

The "doubling" is NOT duplicate data — it's non-standard delisted codes (e.g. `10000` series) that get included when `stock_basic` returns a more complete list. There are NO primary key violations.

### Known Gap Types

1. **Cron silent non-firing** — scheduler doesn't trigger the job on a given day. No error recorded. Only detectable by:
   - Missing output file in `~/.hermes/cron/output/<job_id>/`
   - Database query showing 0 rows for that date
   - `last_run_at` still pointing to a previous day
   - Example: 2026-07-01 for kline pipeline

2. **Script execution failure** — cron fired but script errored. Visible in:
   - `last_status: error` in cron list
   - Script log showing the error
   - Example: 07-03 moneyflow pipeline

3. **Data source freshness delay** — Tushare hasn't published data yet (before ~17:00)
   - Only affects runs before 17:00
   - Returns empty results; script logs show "无数据返回（可能非交易日）"

### Reporting Trigger Words

When these appear in a date's log entry, they indicate known issues:
- "回补" = batch data restoration (moneyflow was backfilled)
- "已有数据，跳过" = duplicate run detected by has_data_for_date() check
- "无数据返回（可能非交易日）" = Tushare API returned empty (data not ready or non-trading day)

## Thresholds for Escalation

| Pipeline | Warning (document) | Critical (escalate) |
|----------|-------------------|---------------------|
| daily_kline | 2+ trading days missing | 5+ trading days missing |
| moneyflow_daily | 3+ trading days missing | 6+ trading days missing |
| index_daily | 1+ trading day missing | 3+ trading days missing |
| valuation | 7+ days stale | 14+ days stale |
