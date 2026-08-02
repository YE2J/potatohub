# TCC Full Disk Access — Granting Hermes External-Drive Access

> **⚠️ CORRECTED 2026-07-31: Full Disk Access does NOT fix session-level TCC lock on
> external volumes.** Verified in production: Hermes.app was added to the FDA list
> (both install locations, toggles ON, app restarted) and a one-shot scheduled cron
> (launchd context) STILL returned `Operation not permitted` / `authorization denied`
> on `/Volumes/500gb/` while the drive was mounted. When the screen is locked or the
> Mac is idle, macOS denies external-volume access from ALL processes — FDA grants,
> process identity, and `disksleep 0` do not override it.
>
> **The real definitive fix for unattended cron:** keep live DBs on the INTERNAL
> drive as real files (not symlinks to /Volumes). External volumes become best-effort
> backup targets only (dual-write with graceful degradation + failure warning).
> See "Session-Level TCC Lock on External Volumes" in the SKILL.md body.
>
> The FDA procedure below remains valid ONLY for interactive-time access (user present,
> screen unlocked). Do not recommend FDA as the fix for scheduled-cron external-drive
> failures.

## FDA Grant Procedure (interactive-time access only)

System Settings → Privacy & Security → **Full Disk Access** → **+** → add ALL of:

| Grant | Path |
|---|---|
| Hermes.app (installed) | `/Applications/Hermes.app` |
| Hermes.app (actually running — check `ps aux \| grep -i hermes`) | `~/.hermes/hermes-agent/apps/desktop/release/mac-arm64/Hermes.app` |
| Real python binary (resolve symlinks!) | `~/.hermes/python-standalone/cpython-3.11.15-macos-aarch64-none/bin/python3` |
| Terminal (optional safety) | `/System/Applications/Utilities/Terminal.app` |

## Critical UI Pitfalls (TCC panel is notoriously flaky)

1. **The popup Finder only shows `.app` files by default** — command-line binaries are
   invisible. Use **Cmd+Shift+G** inside the popup and paste the DIRECTORY path
   (e.g. `.../python-standalone/cpython-3.11.15-macos-aarch64-none/bin/`), then select
   the binary from the list.
2. **Clicking "打开" may silently do nothing** when you selected a symlink or when the
   binary isn't the versioned name. Retry selecting `python3.11` (versioned name).
3. **Drag-and-drop is the most reliable method**: open a normal Finder window at the
   real bin dir, and drag the real binary file into the open Full Disk Access list.
4. **TCC grants the RESOLVED real file, not the symlink.** `venv_cron/bin/python3` is a
   symlink chain (`python3 -> python`); the real file is
   `~/.hermes/python-standalone/.../bin/python3.11`. Resolve with
   `readlink -f ~/.hermes/venv_cron/bin/python3` before adding.
5. After adding, the row must show the toggle **ON** (green). If greyed out, reboot once.
6. **Restart Hermes after granting** — launchd forks only inherit grants after the app
   process restarts.
7. **A binary may appear unselectable / clicking 打开 does nothing** — known macOS 15+
   panel bug with non-.app files. Prefer drag-and-drop (step 3); if the item refuses to
   be added after several attempts, stop burning time on FDA — it is not the fix for
   scheduled-cron external-drive access anyway.

## Distinguishing Disk-Sleep vs TCC Denial vs Session Lock

All three break `/Volumes/` DB access from cron but have different fixes:

| Symptom | Cause | Fix |
|---|---|---|
| sqlite3 **hangs / times out** (3600s cron timeout), `df` fine, access slow | disk sleep (`pmset -g` shows `disksleep N`) | `sudo pmset -a disksleep 0` |
| Instant `Operation not permitted` / `authorization denied`, no hang, **screen unlocked** | FDA grant missing (interactive contexts) | FDA grant (procedure above) |
| Instant `Operation not permitted` / `authorization denied`, no hang, **screen locked / idle** | session-level TCC lock (ALL contexts) | internal-drive migration for cron |

Setting `disksleep 0` does NOT fix TCC denials — they are orthogonal. And FDA does NOT
fix screen-lock denials — session state is orthogonal to process grants.

## Diagnostic Probe Script (schedule as one-shot no_agent cron)

```bash
#!/bin/bash
# ~/.hermes/scripts/diag_external_disk.sh
set -uo pipefail
echo "--- df ---"; df -h /Volumes/500gb
echo "--- mount ---"; mount | grep 500gb
echo "--- ls root ---"; ls -la /Volumes/500gb/
echo "--- ls data ---"; ls -la /Volumes/500gb/data/
echo "--- stat db ---"; stat -f%z /Volumes/500gb/data/stock_data.db
echo "--- sqlite3 direct ---"; /usr/bin/sqlite3 /Volumes/500gb/data/stock_data.db "SELECT 1;"
echo "--- sqlite3 via symlink ---"; /usr/bin/sqlite3 ~/my_quant_system/stock_data.db "SELECT 1;"
```

## Fallbacks

- **Morning report** (read-only consumer): probe DB reachability with
  `timeout 3 sqlite3 "$DB" "SELECT 1;"`; on failure copy the latest local backup
  (`~/my_quant_system/backups_local/stock_data_*.db`) to `/tmp/stock_data_morning.db`
  and export `MORNING_DB_PATH` for the Python script (env-var override in the script).
- **Write-heavy pipelines** (ingestion engines): cannot run against a stale copy —
  the DB must live on an internal drive.
