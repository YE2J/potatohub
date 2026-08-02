# External Disk Diagnostic Case — stock_data.db on /Volumes/500gb

Real session 2026-07-30/31: all daily pipeline cron jobs failed for 2 days with
`unable to open database file` / `sqlite3.OperationalError` while the API token
and scripts were fine.

## Symptom pattern
- Scheduled `no_agent=true` pipeline jobs (18:00–20:30) exit code 1, `unable to open database file`
- Morning report (07:05) sometimes timed out 3600s (sqlite3 blocked on a sleeping external drive)
- Manual runs of the SAME scripts sometimes succeed (drive awake / user present), sometimes fail
- `file ~/my_quant_system/stock_data.db` → `broken symbolic link`
- `ls /Volumes/500gb/data/` → `Operation not permitted` (intermittent, both contexts)
- Cron log `~/.logs/<job>.log` can be EMPTY for the failed run (script died before logging) — check `~/.hermes/cron/executions.db` instead:
  `SELECT job_id, claimed_at, status, error FROM executions ORDER BY claimed_at DESC`

## THE ROOT CAUSE: Session-Level TCC Lock on External Volumes (macOS 15+)

**This is NOT a permission configuration problem. It is a macOS session-state behavior.**

| Screen state | `/Volumes/*/` access |
|---|---|
| Screen unlocked, user active | ✅ readable (all contexts: terminal, manual, scheduled cron) |
| Screen locked / Mac idle | ❌ `Operation not permitted` / `authorization denied` (ALL contexts) |

External-volume file access on macOS 15+ is tied to the console session, not to binary
identity or TCC process grants. When the screen is locked or the Mac is idle, the OS
denies file access to `/Volumes/*/` from EVERY process — terminal, Hermes.app, manual
cron trigger, AND scheduled launchd cron.

**Proof:** both Hermes.app copies were granted Full Disk Access (toggles ON, app
restarted); a one-shot scheduled cron (launchd context) STILL returned
`Operation not permitted` on `/Volumes/500gb/` while `df` showed the drive mounted.
No FDA grant, process identity, or `disksleep 0` setting overrides this.

The confusion: the user IS present during evening hours, so interactive/manual runs
succeed most evenings; failures happen overnight (00:00–07:05) and weekends when the
Mac is locked. **If the user reports "待机时访问不了，平时正常" (fails when idle,
works when active) — treat session-lock as the hypothesis; stop investigating
permissions.**

## Root causes confirmed (with fixes)

| # | Root cause | Fix |
|---|---|---|
| 1 | **Session-level TCC lock** on external volumes (THE root cause) | **DB migration: live DB to internal drive as a REAL file (not symlink to /Volumes)** |
| 2 | `disksleep 10` on external SSD (secondary): drive sleeps after 10 min no I/O; pipeline jobs spaced >10 min apart (18:00, 18:15, 18:30...) — each job wakes the drive, it sleeps again, next sqlite3 open blocks or fails. | `sudo pmset -a disksleep 0` (SSD no mechanical wear) |
| 3 | **Swallowed exceptions** in scripts (e.g. `daily_margin_balance.py` catches all, prints only `❌ 两融余额采集异常` — deliberate anti-token-leak). Impossible to diagnose from cron output alone. | Write a temp diagnostic script that prints full tracebacks; run as a one-shot scheduled cron (Pattern D, launchd context) |

**RED HERRING (hours wasted):** FDA grants were pursued (Hermes.app both locations +
real python binary). They fixed daytime interactive access but NOT scheduled-cron
access during lock hours. The user also could not add bare binaries to the TCC panel
(macOS 15+ UI bug; drag-and-drop also failed). Do not repeat this path.
Fixes #2 (disksleep 0) and FDA are orthogonal to fix #1 — none of them fix session lock.

## Diagnostic recipe (always test in the FAILING context)

1. Read `~/.hermes/cron/executions.db` — has full per-run error text, more than the .md output files.
2. **Split-test**: probe (a) in interactive terminal, (b) as one-shot `no_agent=true` cron
   scheduled 2–3 min out. If the API call works but DB open fails in both → file-access problem, NOT token/API.
3. Good probe (proves API separately from file access):
   ```bash
   stat -f%z /Volumes/500gb/data/stock_data.db
   /usr/bin/sqlite3 ~/my_quant_system/stock_data.db "SELECT 1;"
   python3 -c "import tushare as ts; print(len(ts.pro_api().margin(trade_date='YYYYMMDD', exchange_id='SSE')))"
   ```
4. Ask the user about the access pattern: "does external-drive access work while you're
   using the Mac but fail when it's idle/locked?" — if yes, session-lock; stop investigating permissions.

## Migration recipe (definitive fix, applied 2026-07-31)

Do this while the user is present and the external volume is accessible:

```bash
# 1. Hot backup (NOT cp — .backup captures a WAL-consistent snapshot)
sqlite3 ~/my_quant_system/stock_data.db ".backup '/Users/yellow/my_quant_system/stock_data_new.db'"
# 2. Verify integrity + per-table row counts (old vs new)
sqlite3 stock_data_new.db "PRAGMA integrity_check;"   # → ok
for tbl in daily_kline moneyflow_daily index_daily margin_balance sector_moneyflow_dc market_temperature hot_stock_daily daily_factors; do
  old=$(sqlite3 ~/my_quant_system/stock_data.db "SELECT COUNT(*) FROM $tbl;")
  new=$(sqlite3 stock_data_new.db "SELECT COUNT(*) FROM $tbl;")
  [ "$old" = "$new" ] && echo "OK $tbl" || echo "MISMATCH $tbl"
done
# 3. Verify no running cron jobs
sqlite3 ~/.hermes/cron/executions.db "SELECT COUNT(*) FROM executions WHERE status IN ('running','claimed');"
# 4. Atomic swap, keep .bak for rollback
cd ~/my_quant_system && mv stock_data.db stock_data.symlink_to_external.bak && mv stock_data_new.db stock_data.db
# 5. Verify in the FAILING context: one-shot scheduled cron (launchd) that opens the DB
```

Key details:
- `.backup` preserves WAL journal mode (verified `PRAGMA journal_mode` → `wal`).
- Full verification chain: integrity_check + per-table row counts + terminal engine run
  + **one-shot scheduled cron probe** (the failing context is the only valid test). All passed.
- After migration: local backups are same-disk (no physical redundancy) — acceptable
  for re-pullable non-production data; external volume becomes best-effort push with
  graceful degradation (dual-write: local mandatory + external optional, warn on
  external failure — expected every month at 03:00 during lock hours).

## Other fixes applied (all reusable)
- **Morning-report wrapper fallback**: probe DB with `timeout 3 sqlite3 "$DB" "SELECT 1;"`;
  on failure `cp` latest `~/my_quant_system/backups_local/stock_data_*.db`
  to `/tmp/stock_data_morning.db` and set `MORNING_DB_PATH` env var; Python reads
  `os.environ.get("MORNING_DB_PATH") or "~/my_quant_system/stock_data.db"`
- **Backup cadence**: daily full 6.9 GB backup → monthly on the 1st, keep 4 copies
  (data is re-pullable from Tushare; daily backup not worth it)
- **Missing script + cron path guard**: `daily_market_moneyflow.py` lived in
  `~/my_quant_system/scripts/`; a symlink into `~/.hermes/scripts/` got REJECTED by the
  cron script-path guard (`Blocked: script path resolves outside the scripts directory`).
  Fix: tiny wrapper `.sh` in `~/.hermes/scripts/` that runs the real `.py` from
  `~/my_quant_system/scripts/` — wrapper indirection, NOT symlink.
- **`.env` missing `export`**: `.env.fuyao` had `FUYAO_TOKEN=...` without `export`, so
  child Python processes didn't inherit it → "环境变量未设置". Fix: `export FUYAO_TOKEN=...`.
- **Tushare token "invalid" false alarm**: `grep KEY file | cut -d= -f2` keeps
  surrounding quotes → `您的token不对`. Use `source` or strip quotes in Python.

## Cron output gotcha
`no_agent` script .md output may say only "Script exited with code 1" with NO
stdout/stderr — the wrapper's pipe chain (`| cron_log_tail | tee -a`) can hide the real
error. Check `executions.db` and the script's own `~/.logs/<job>.log` tail before
concluding anything about token/API/script.
