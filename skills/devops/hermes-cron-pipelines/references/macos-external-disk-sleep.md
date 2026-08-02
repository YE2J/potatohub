# macOS External Disk Sleep → Cron Pipeline Failure

## Root Cause Pattern

When the SQLite database is on an external volume via symlink:

```
stock_data.db → /Volumes/ExtDrive/data/stock_data.db
```

macOS `disksleep` (default 10 min) sleeps the external drive after inactivity.
Cron scripts that access the DB via `sqlite3.connect()` may fail **before** the
disk finishes waking up, producing:

```
sqlite3.OperationalError: unable to open database file
```

## Symptoms

- Cron jobs exit code 1 with NO stdout (sqlite3 fails before any logging)
- `executions.db` shows `unable to open database file` in `error` column
- Jobs with >10min gaps between them tend to fail in cascade
- Same script works when run manually (disk already awake from user activity)
- Morning-report & overnight jobs are most vulnerable

## Diagnostic Ladder

1. **Check executions.db** — the cron scheduler's `executions.db` stores
   actual stderr, which cron output files often don't capture:
   ```bash
   sqlite3 ~/.hermes/cron/executions.db "SELECT job_id, claimed_at, status, error FROM executions ORDER BY claimed_at DESC LIMIT 40;"
   ```

2. **Verify disk sleep state:**
   ```bash
   pmset -g | grep disksleep
   # disksleep 10 → will sleep after 10 min idle
   # disksleep 0  → never sleeps
   ```

3. **Quick accessibility test** (3-second timeout):
   ```bash
   timeout 3 sqlite3 "$DB_PATH" "SELECT 1;" && echo "accessible" || echo "sleeping"
   ```

## Fixes (ordered by preference)

### Option A: Disable disk sleep permanently (cleanest)
```bash
sudo pmset -a disksleep 0
```
Safe for SSDs (no mechanical wear). Persists across reboots.

### Option B: Shell-wrapper fallback (for scripts)
Add a DB accessibility probe before running the main script:
```bash
if ! timeout 3 sqlite3 "$DB_PATH" "SELECT 1;" >/dev/null 2>&1; then
    LATEST_BACKUP=$(ls -t "$LOCAL_BACKUP_DIR"/stock_data_*.db 2>/dev/null | head -1)
    if [ -n "$LATEST_BACKUP" ]; then
        cp "$LATEST_BACKUP" /tmp/stock_data_fallback.db
        DB_PATH="/tmp/stock_data_fallback.db"
    else
        echo "DB inaccessible and no backup available" >&2
        exit 1
    fi
fi
export DB_PATH
# or set a custom env var that Python scripts check (e.g. MORNING_DB_PATH)
```

### Option C: Time gap mitigation
If `disksleep=0` is not an option, ensure pipeline jobs are scheduled
with <10min gaps to prevent the disk from sleeping mid-pipeline.

## Reference: cron execution DB schema
```sql
CREATE TABLE executions (
    id TEXT PRIMARY KEY, job_id TEXT NOT NULL, source TEXT NOT NULL,
    process_id TEXT NOT NULL, pid INTEGER NOT NULL,
    process_started_at INTEGER, status TEXT NOT NULL,
    claimed_at TEXT, started_at TEXT, finished_at TEXT, error TEXT
);
```
