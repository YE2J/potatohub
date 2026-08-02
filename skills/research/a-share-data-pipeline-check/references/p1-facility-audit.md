# P1 Data Facility Audit (2026-07-09)

## Summary

Reviewed all 5 dimensions of the P1 data facility against the production database. Found 2 red-level and 3 yellow-level issues.

## Findings

### 🔴 6 of 7 New Tables Are Empty

| Table | Row Count | Status |
|-------|-----------|--------|
| market_temperature | 0 | Empty |
| sector_rotation | 0 | Empty |
| leader_stocks | 0 | Empty |
| decision_log | 0 | Empty |
| valuation_daily_signal | 0 | Empty |
| drawdown_log | 0 | Empty |
| valuation_sector_config | 25 | Populated |

Only `valuation_sector_config` (the lookup table) has data. All 6 analytical/aggregation tables are empty — the L1→L2→L3 computation pipeline was never wired up.

### 🟡 Cron Timing: THS Moneyflow at 16:00 is Too Early

The cron `板块资金流向-每日增量` (job_id=9139d87aa0e2) runs at `0 16 * * 1-5` with script `daily_sector_moneyflow.py`. But:

- Tushare's `moneyflow_cnt_ths` / `moneyflow_ind_ths` APIs typically update **17:00–19:00**
- DC moneyflow cron is set at **18:30** — acknowledging the later update time
- The script uses `yesterday = datetime.now() - timedelta(days=1)` — this fetches the **previous calendar day**, not the previous trading day. Skips Friday→Monday, holiday gaps.

**Fix**: Move to 18:30+ and use `pro.trade_cal()` to find the actual previous trading day.

### 🔴 ALL Cron Jobs in Failed State

Every `cron_push_log` entry shows `status=failed` with error `zombie: old cron_log_helper bug`. This is a known macOS `date +%s%3N` issue in `cron_log_helper.sh` — the BSD date appends `3N` as literal text, making the integer comparison fail. Pipeline scripts themselves may succeed, but the helper wrapper exits 1, making Hermes record `last_status: error`.

### 🟡 `daily_sector_moneyflow.py` — `to_sql(append)` PK Conflict Bug

The script (line 27) uses:
```python
df.to_sql(table, conn, if_exists='append', index=False)
```
Both `sector_moneyflow_ths` and `industry_moneyflow_ths` have `PRIMARY KEY (trade_date, sector_code)`. If the backfill already covers the target date, `append` mode will crash with a UNIQUE constraint violation. Should use `INSERT OR REPLACE` via cursor iteration.

### 🟡 Valuation Sector Coverage: 25/90 Industries Configured

Only 25 of ~90 THS industries have model mappings in `valuation_sector_config`. Missing include: 电池, 风电设备, 元件, IT服务, 军工电子, 汽车零部件, and ~60 more. Stocks in uncovered industries get no `valuation_daily_signal`.

### ✅ JOIN Key Compatibility Verified

- `ths_member.ts_code` ↔ `sector_moneyflow_ths.sector_code`: both use `885xxx.TI` / `881xxx.TI` format ✓
- 289 concept codes: 288 matched, 1 missing (885940.TI — 四川九洲, possibly a new listing)
- 90 industry codes: 90/90 matched ✓

### ✅ No DC/TDX Coverage (Known Gap)

No `dc_*` or `tdx_*` tables exist in the database. Only THS sector data is collected. The DC moneyflow cron covers individual stock moneyflow only, not sector-level.
