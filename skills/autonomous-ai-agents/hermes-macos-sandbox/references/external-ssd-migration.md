# External SSD Database & Data Migration Pattern

## When to Use

- Moving large files (databases > 500Mi, data archives) from internal SSD to external removable media
- Need zero-code-change operation (symlink at original path)
- External drive is a fast SSD (>200MB/s write speed)

## Critical Prerequisite: Speed Test

Always test the external drive speed first — determines whether symlinked databases are viable:

```bash
dd if=/dev/zero of=/Volumes/<DRIVE>/speed_test.tmp bs=1m count=100 2>&1 | tail -1
```

| Speed | Verdict | Migration Strategy |
|-------|---------|-------------------|
| **>200 MB/s** | SSD/NVMe — safe | cp → verify → mv + symlink (file lives on external) |
| **50–200 MB/s** | Mid-range USB | Keep local copy; use external for cold backup only |
| **<50 MB/s** | HDD | DO NOT symlink — use rsync backup to external, keep file local |

## Pattern: cp → verify → symlink (SSD-safe)

```bash
# 1. Copy to external drive
cp ~/project/source.db /Volumes/<DRIVE>/data/source.db

# 2. Verify file sizes match
ls -la ~/project/source.db /Volumes/<DRIVE>/data/source.db

# 3. Very fast integrity check (skip for 1Gi+ files — too slow)
sqlite3 /Volumes/<DRIVE>/data/source.db "PRAGMA quick_check;" 2>/dev/null
# For large DBs: just check that SQLite can read it
sqlite3 /Volumes/<DRIVE>/data/source.db ".tables" 2>/dev/null | head -3

# 4. Rename original (backup safety net)
mv ~/project/source.db ~/project/source.db.localbak

# 5. Create symlink at original path
ln -s /Volumes/<DRIVE>/data/source.db ~/project/source.db

# 6. Verify symlink works
ls -la ~/project/source.db
sqlite3 ~/project/source.db ".tables" 2>/dev/null | head -3

# 7. Delete local backup only AFTER confirming everything works
rm ~/project/source.db.localbak
```

## macOS TCC Sandbox Note

The terminal agent's `cp` and `mv` to `/Volumes/*/` work ONLY when the user is present at the computer to approve the macOS TCC prompt. If the user is away, attempt `mkdir` first — if it fails with `Operation not permitted`, wait for the user to return.

## Symlink Compatibility

- **Python `open()`**: Transparent ✅
- **SQLite**: Transparent ✅
- **`os.path.join(os.path.dirname(__file__), "db_name.db")`**: Transparent ✅
- **Cron jobs**: Transparent (external drive must be mounted before cron runs)
- **Bash `test -f`**: Transparent ✅

## Failure Mode: External Drive Unplugged

When the external drive is disconnected:
- Symlinks show as broken (`ls -la` shows red/blinking target)
- Any tool/script accessing the path gets `No such file or directory`
- **Solution**: Check mount before accessing: `[ -d /Volumes/<DRIVE> ] || echo "External drive not mounted"`

## Downloads Auto-Archive Watchdog (no_agent=true Cron)

Pattern for recurring cleanup: shell script + no_agent=true cron + silent-when-empty delivery.

The script at `~/.hermes/scripts/archive_downloads.sh`:
- Scans `~/Downloads` for files older than 30 days
- Moves to `/Volumes/<DRIVE>/archives/YYYY-MM/`
- Silent (no delivery) when nothing to archive
- Reports file list + sizes when something is moved

Cron config (set via cronjob tool):
```yaml
schedule: "0 9 * * 0"    # Weekly Sunday 09:00
no_agent: true            # Script stdout = delivery content
script: archive_downloads.sh
```

Key design choices:
- `while IFS= read -r -d ''` — null-delimited for safe filenames (spaces, unicode)
- `stat -f "%Sm" -t "%Y-%m"` — macOS-specific date extraction
- Exit 0 on unmounted drive (silent skip, not error alert)
- `COUNT` accumulator + conditional output at end (empty = silent)
