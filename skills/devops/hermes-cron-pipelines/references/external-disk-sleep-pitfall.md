# macOS External Disk Sleep — Cron Pipeline Pitfall

## Problem

macOS spins down external drives (USB-C, Thunderbolt, SSD enclosures) after ~10 minutes of inactivity (`pmset -g disksleep`). When a cron job opens a file on the mounted external drive through a symlink, the I/O request blocks until the disk spins back up. On some drives, this wake-from-sleep I/O can:

- Take 30-120 seconds (annoying but recoverable)
- **Hang indefinitely** (the most dangerous case — causes 3600s cron timeout)
- Return "Operation not permitted" or "authorization denied" via TCC when the disk backend is in a transitional state

This is **not** a TCC sandbox issue — it's a macOS power management × filesystem stack interaction.

## Affected Pattern

```
~/my_quant_system/stock_data.db  →  symlink  →  /Volumes/500gb/data/stock_data.db
                                                          ↑
                                                    external disk (sleep-prone)
```

Any cron job that reads `stock_data.db` between ~21:00 and ~08:00 is vulnerable (10+ hours of inactivity after the daily pipeline finishes at 20:30).

## Symptoms in Cron Output

| Symptom | Meaning |
|---------|---------|
| `Script timed out after 3600s` | sqlite3 blocked waiting for disk I/O, never returned |
| `unable to open database file` | Disk in transitional state, sqlite3 got EACCES/EIO |
| `authorization denied` | macOS TCC returned transient denial during wake cycle |
| `Script exited with code 1` + only `=== ... 开始 ===` line | `PRAGMA integrity_check` or `stat` failed on sleeping disk |

## Detection

```bash
# Check disk sleep timeout (0 = never sleep, 10 = 10 min)
pmset -g | grep disksleep

# Check if disk is spun down (very quiet = sleeping)
diskutil info /Volumes/500gb | grep -i "sleep\|idle"

# Minimal reachability test (3s timeout)
if ! timeout 3 sqlite3 "$DB_PATH" "SELECT 1;" >/dev/null 2>&1; then
    echo "⚠️ External disk unreachable (sleeping?)" >&2
fi
```

## Fix Pattern: Timeout + Fallback

### Shell wrapper probe (recommended for all cron scripts that read the DB)

Add this to any shell wrapper that reads `stock_data.db`:

```bash
DB_PATH="$HOME/my_quant_system/stock_data.db"
DB_FALLBACK_DIR="$HOME/my_quant_system/backups_local"
ACTIVE_DB="$DB_PATH"

if ! timeout 3 sqlite3 "$DB_PATH" "SELECT 1;" >/dev/null 2>&1; then
    LATEST_BACKUP=$(ls -t "$DB_FALLBACK_DIR"/stock_data_*.db 2>/dev/null | head -1)
    if [ -n "$LATEST_BACKUP" ]; then
        cp "$LATEST_BACKUP" /tmp/stock_data_morning.db 2>/dev/null
        ACTIVE_DB="/tmp/stock_data_morning.db"
    else
        echo "❌ DB unreachable and no local backup" >&2
        exit 1
    fi
fi
# Use $ACTIVE_DB as the database path downstream
```

### Python script — env var override

In Python scripts that hardcode the DB path, add an env var override line:

```python
DB_PATH = os.environ.get("MORNING_DB_PATH") or os.path.expanduser("~/my_quant_system/stock_data.db")
```

Then in the shell wrapper, set `MORNING_DB_PATH` when the fallback kicks in.

## Prevention

| Approach | Effort | Reliability |
|----------|--------|-------------|
| `pmset -c disksleep 0` (prevent sleep while on AC) | Low | High (AC only) |
| Monthly backup schedule (reduce exposure) | Low | Medium |
| Timeout probe + fallback to local backup | Medium | High |
| Keep a cron job that touches the disk every 30min | Low | Medium (wakes disk unnecessarily) |

## Example: DB Backup Schedule Change

A pipeline running `0 3 * * *` (daily 03:00) on an external disk DB will fail most days. Change to `0 3 1 * *` (monthly 1st) — far fewer sleep-trigger opportunities, and data loss risk is low since all data is API-recoverable.

## References

- `pmset(1)` — macOS power management settings
- `diskutil(8)` — disk management
- `Hermes MacOS Sandbox` references for TCC vs disk-sleep distinction
