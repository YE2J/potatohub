# Case Study: External-Drive Session-Lock → DB Migration + Morning Report Double-Bug

Timeline from 2026-07-30..08-02 on the user's macOS 15+ quant system
(`~/my_quant_system/stock_data.db`, ~6.5 GB SQLite, WAL mode).

## Symptom pattern

- 18:00–20:30 weekday pipeline cron jobs ALL failed with `unable to open database file`
  while the identical scripts succeeded when run manually moments later.
- Morning report (07:05) intermittently: `unable to open database file`, 3600s timeout,
  then silently served 3-day-old data.
- User's own words were the key diagnostic: "待机时访问不了，平时正常" (can't access
  when idle, works during normal use).

## Root cause: session-level TCC lock (NOT disk sleep, NOT per-process grant)

- External volume `/Volumes/500gb` was mounted (`df` fine, `mount` fine) but file
  access returned `Operation not permitted` / `authorization denied` from EVERY
  context — interactive terminal, Hermes.app, manual cron trigger, AND scheduled
  launchd cron — **whenever the screen was locked/idle**.
- `sudo pmset -a disksleep 0` did NOT fix it (drive never slept; TCC blocked access).
- Granting Hermes.app Full Disk Access (both install paths) did NOT fix it; TCC panel
  refuses CLI binaries (python3.11 could not be added — grayed out) anyway.
- Concluded: external-volume access is tied to the console session, not the binary
  identity. No FDA grant overrides it.

## The fix that worked: migrate DB to internal drive

```bash
# 1. Hot backup (preserves WAL consistency; DO NOT use cp for a live WAL db)
sqlite3 ~/my_quant_system/stock_data.db ".backup '~/my_quant_system/stock_data_new.db'"

# 2. Verify: integrity + row counts per table (old vs new must match)
sqlite3 ... "PRAGMA integrity_check;"   # → ok
# compare COUNT(*) per table

# 3. Atomic swap keeping rollback
mv ~/my_quant_system/stock_data.db ~/my_quant_system/stock_data.symlink_to_external.bak
mv ~/my_quant_system/stock_data_new.db ~/my_quant_system/stock_data.db

# 4. Verify in the FAILING context (one-shot scheduled cron, not terminal)
#    → launchd-context read/write test passed after migration
```

External drive then demoted to best-effort backup target: monthly backup script writes
local (mandatory, keep 4) + external (best-effort, keep 4, warn on failure — expected
to fail at 03:00 while screen locked).

## Second bug that masked the fix: GNU `timeout` absent on macOS

Morning report wrapper had an "external-drive sleep protection" probe:

```bash
if ! timeout 3 sqlite3 "$DB" "SELECT 1;" >/dev/null 2>&1; then
    # fallback: cp latest backups_local/*.db to /tmp and read that
fi
```

macOS has no `timeout` → exit 127 → **fallback always taken** → report read the stale
backup (data 3 days old) even after migration made the real DB fully reachable. Fix:
delete the dead fallback branch entirely (DB is internal now) and point directly at
the internal DB. Also caught in the same session: `timeout` is not the only GNU-ism —
`numfmt` also absent (use `bc`); verify with `command -v` before relying.

## Third bug (Sunday-only): `:d` format on a float

`daily_morning_report_v7.py` weekly summary used
`f"...({diff:+d})"` where `diff = last_temp - first_temp` is a float →
`Unknown format code 'd' for object of type 'float'` → whole report crashed, but ONLY
on Sunday (the code path only runs in the Sunday "本周总结" branch). Saturday full
report worked. Fix: `{diff:+.1f}`. Lesson: when a report has weekday-specific
branches, test each branch — a bug can live for weeks in a rarely-executed path.

## Key takeaways

1. External `/Volumes/*/` reachability varies with the console session. Verify access
   IN THE SAME CONTEXT that failed (one-shot cron), not in the terminal.
2. `unable to open database file` in cron ≠ token/API/script problem. First isolate
   whether the DB file is reachable in that context.
3. After any migration, REMOVE the fallback code built for the old topology — stale
   fallbacks silently mask whether the fix worked.
4. Wrappers that swallow exceptions (`except Exception: print('❌ ...')`) turn real
   errors into "Script exited with code 1" with no traceback. Use a diagnostic script
   that prints full tracebacks when the cause is unknown.
5. User's own natural-language observation ("works when I'm using it, fails when
   idle") was the decisive diagnostic — ask for it early.
