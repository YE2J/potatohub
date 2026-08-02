# ETL Script Audit Checklist

A re-usable checklist for auditing a cron-driven Python ETL script that reads from an external API and writes to SQLite. Use as a reference when a user asks you to "review," "audit," or "inspect" a data-pipeline script.

---

## 1. API Key / Credential Security

- [ ] Key files stored with `0600` permissions (owner-only read/write)
- [ ] Key read via `open(f).read().strip()` with length/format validation
- [ ] No key ever printed to stdout/stderr or logged
- [ ] Key rotation / dual-key support present (round-robin between multiple keys)
- [ ] Error message on missing key exits cleanly (not crashing with traceback)

## 2. Shell Wrapper Script

- [ ] Uses `set -euo pipefail` for strict error handling
- [ ] Pre-flight check: verifies Python script exists (`[ -f "$SCRIPT" ]`) before running
- [ ] Pipe protection: uses `|| true` on piped commands to prevent `set -o pipefail` silent exits
- [ ] Captures `PIPESTATUS[0]` immediately after piped command (e.g., `$PYTHON script.py 2>&1 | tee -a log`)
- [ ] Uses `trap cleanup EXIT` to remove temp files
- [ ] Resolves script directory via `${BASH_SOURCE[0]}` for portability
- [ ] Log rotation: daily file (`job_YYYYMMDD.log`) or `newsyslog` config (not unbounded single-file append)
- [ ] Stderr redirected: `2>&1 | tee -a`
- [ ] Exit code propagated correctly

## 3. Python ETL Core

- [ ] Schema alignment: `PRAGMA table_info()` column list matched against INSERT column list (no `total_inflow`/`total_outflow` dangling references)
- [ ] `data_source` handling: not hardcoded in a way that erases other sources' origin tags
- [ ] `INSERT OR REPLACE` PK exists and is correct — verified against actual table schema
- [ ] `last_insert_rowid()` / `lastrowid` captured correctly from cursor, not from a separate `execute()` call
- [ ] Uses `etl_helpers.etl_run()` context manager or equivalent for run tracking
- [ ] Uses `etl_runs` table for status (not writing to orphan files like `failed_dates.txt`)
- [ ] Idempotent: re-running the same date produces no duplicates and no data loss
- [ ] Partial-failure safe: if the script dies mid-batch, re-running recovers correctly

## 4. Error Handling & Resilience

- [ ] HTTP request timeout set (not relying on system default)
- [ ] Retries with backoff for transient API failures
- [ ] Rate limiting: respects API provider request limits (sleep between batches)
- [ ] Graceful degradation: if primary source fails, tries fallback (or reports clearly)
- [ ] API error response bodies not leaked to log (may contain secrets)

## 5. Ops & Monitoring

- [ ] Dry-run mode (`--dry-run` flag that skips INSERT and prints summary)
- [ ] Meaningful per-stock progress output (not just "ok" or empty)
- [ ] Final summary line: `total=X ok=Y fail=Z elapsed=Ts`
- [ ] Log timestamp format present and consistent
- [ ] No orphan files written but never read (check all `open("...", "a")` calls)

## 6. Cron Integration

- [ ] Cron schedule avoids overlap with other jobs writing to same DB (≥1h gap recommended)
- [ ] Script path in crontab matches actual filesystem location
- [ ] STDOUT redirect in cron entry matches log file path
- [ ] Delivery mode chosen correctly (`origin` for user-facing, `local` for silent ops)
- [ ] If consolidating into daily morning report: output is parseable by aggregator script

## 7. Cross-Pipeline Coordination

- [ ] Multiple cron jobs writing to the same table use staggered schedules
- [ ] Compound PK `(stock_code, date, data_source)` considered if per-source rows are needed
- [ ] OR separate pipelines update disjoint column sets via UPSERT/MERGE
- [ ] Downstream queries know which `data_source` to filter on

---

## Quick-Reference: Common DB Schema Mismatches

| Symptom | Likely Cause |
|---------|-------------|
| `sqlite3.OperationalError: table moneyflow_daily has no column named total_inflow` | INSERT lists column that doesn't exist in `PRAGMA table_info()` |
| `sqlite3.OperationalError: table moneyflow_daily has 27 columns but 29 values were supplied` | INSERT value count exceeds actual column count |
| `data_source` flips between 'eastmoney' and 'iwencai' on re-run | `INSERT OR REPLACE` overwrites entire row including metadata |
| `last_insert_rowid()` returns 0 or wrong run_id | Used in a separate `execute()` call instead of `cur.lastrowid` |
| `failed_dates.txt` has 100s of lines but script never reads it | Orphan file — written to but never consumed |
| Script takes 3x expected time on Monday | API rate limiting after weekend backfill backlog; no break between batches |
