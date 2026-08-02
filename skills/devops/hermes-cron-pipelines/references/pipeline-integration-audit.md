# Pipeline Integration Audit — Review D Findings

> Date: 2026-07-09
> Pipeline: Tushare API → 6 cron pipelines → 5 core tables → morning report (agent cron, 07:05) → WeChat

## Timeline of Pipelines

```
15:30~22:00  Financial-API (fuyao): limit_up_pool, limit_up_ladder, daily_anomaly, dragon_tiger_daily, hot_stock_daily
18:00        qfq daily → daily_kline
18:15        Index daily → index_daily
18:30        Moneyflow DC → moneyflow_daily
19:00        Factor update → daily_factors (depends on daily_kline + moneyflow_daily)
20:00        Factor backfill → daily_factors (depends on daily_factors)
07:05        Morning report (reads all above + ~/.logs/ + ~/.hermes/cron/output/)
```

## Issues Found

### E1: 🔴 P0 — `.env.fuyao` File Missing

**Symptom**: 5 Financial-API cron wrapper scripts (`daily_limit_up_fuyao.sh`, `daily_limit_up_ladder.sh`, `daily_anomaly_fuyao.sh`, `daily_dragon_tiger_fuyao.sh`, `daily_hot_stock_fuyao.sh`) all try to source `$HOME/.hermes/.env.fuyao` as a fallback for `FUYAO_TOKEN`. This file does **not exist**.

**Root cause**: Wrapper scripts were refactored from inline hardcoded tokens to file-based tokens, but the `.env` file was never created.

**Impact**: If `FUYAO_TOKEN` is not available from the Hermes gateway process environment, all 5 Financial-API crons fail silently with `RuntimeError: 环境变量 FUYAO_TOKEN 未设置`.

**Fix**: Create `~/.hermes/.env.fuyao` with content `FUYAO_TOKEN=sk-xxx` and `chmod 600`.

### E2: 🟡 P1 — Financial-API Log Files Not Checked by Morning Report

**Symptom**: `report_data_status()` (v5.py lines 283-287) checks only 3 log files: `qfq_tushare.log`, `moneyflow_tushare_dc.log`, `tushare_index.log`. The 5 Financial-API pipeline log files (`limit_up_fuyao.log`, `limit_up_ladder.log`, `anomaly_fuyao.log`, `dragon_tiger_fuyao.log`, `hot_stock_fuyao.log`) are **not monitored**.

**Root cause**: The morning report's log file list is static. Adding new pipelines that write their own log files doesn't automatically update the check.

**Impact**: If any Financial-API cron fails, the morning report shows "✅ All channels OK" — a false sense of completeness.

**Fix**: Add the 5 fuyao log files to the `pipelines` list in `report_data_status()`.

### E3: 🟡 P1 — `daily_index_tushare.sh` Passes Empty job_id

**Symptom**: `cron_log_init "指数日线-Tushare增量" "" "18:00" "local"` — the second argument (job_id) is an empty string. The `cron_push_log.cron_log` column stores `NULL`.

**Root cause**: Copy-paste error during wrapper script creation; the canonical 12-char hex job_id `5575f1bae80e` was never filled in.

**Impact**: `cron_push_log` records for the index pipeline cannot be joined against `jobs.json`. Any diagnostic that relies on `WHERE job_id = '5575f1bae80e'` misses these rows.

**Fix**: Change to `cron_log_init "指数日线-Tushare增量" "5575f1bae80e" "18:00" "local"`.

### E4: 🟡 P1 — `daily_sector_moneyflow.sh` Has No cron_log_helper Integration

**Symptom**: The sector moneyflow wrapper is a bare 16-line script with no `cron_log_init`/`cron_log_finish` calls, no structured logging, no `set -u`.

**Root cause**: Was originally configured directly as `script: daily_sector_moneyflow.py` in jobs.json (no wrapper). Later switched to a `.sh` wrapper but only the bare minimum was added.

**Impact**: Sector moneyflow runs exist independently of the cron_push_log system. Failures are not recorded in the central audit trail.

**Fix**: Add full cron_log_helper integration (same pattern as the fuyao wrappers).

### E5: 🟡 P2 — `get_latest_trade_date()` Queries Wrong Table

**Symptom**: `get_latest_trade_date()` in `daily_morning_report_v5.py` (line 225-234) queries `SELECT MAX(date) FROM moneyflow_daily`. This returns the latest date for which moneyflow data exists, NOT the latest trading day.

**Root cause**: The function was written for a specific use case (moneyflow report) but is used as a general "latest trading day" indicator throughout the morning report.

**Impact**: If moneyflow data is delayed but k-line data is current, the morning report shows an incorrectly old date. The `report_yesterday_tasks()` module labels all outputs with this wrong date.

**Fix**: Either (a) query `trade_cal` for the authoritative latest trading day, or (b) take MIN(max_date) across all data tables.

## Verification Commands

```bash
# Check all log files exist and are monitored
ls ~/.logs/*.log
grep -oP '"[a-z_]+\.log"' ~/.hermes/scripts/daily_morning_report_v5.py

# Check all wrapper scripts have cron_log_helper integration
grep -l "^#.*cron wrapper" ~/.hermes/scripts/*.sh | while read f; do
  init=$(grep -c "cron_log_init" "$f")
  finish=$(grep -c "cron_log_finish" "$f")
  id=$(grep -cP 'cron_log_init\s+"[^"]+"\s+"[a-f0-9]{12}"' "$f" || echo 0)
  echo "$(basename $f): init=$init finish=$finish correct_id=$id"
done

# Check env files exist for all service tokens
for svc in tushare fuyao; do
  [ -f "$HOME/.hermes/.env.$svc" ] && echo "✅ .env.$svc" || echo "🔴 MISSING .env.$svc"
done

# Check all data source dates are consistent
sqlite3 ~/my_quant_system/stock_data.db "
  SELECT 'moneyflow_daily' as tbl, MAX(date) as latest FROM moneyflow_daily
  UNION ALL SELECT 'daily_kline', MAX(date) FROM daily_kline
  UNION ALL SELECT 'index_daily', MAX(trade_date) FROM index_daily
  UNION ALL SELECT 'trade_cal', MAX(cal_date) FROM trade_cal WHERE is_open = 1;
"
```
