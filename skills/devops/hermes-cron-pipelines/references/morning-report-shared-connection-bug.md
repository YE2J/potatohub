# Case: cron "ok" but downstream consumer fails — shared SQLite connection closed by one module

## Symptom (2026-08-11)
- 大盘温度 cron (`e5e967ea3aeb`, no_agent, `engines/market_temperature.py`) reported `last_status: ok` and the data WAS written: `market_temperature` had 2026-08-10 row (温度=53.2).
- User said "大盘温度失败了" — the actual failure was in the 07:05 morning report (`daily_morning_report_v7.py`): `## 🌡️ 大盘温度 > ❌ 查询失败: Cannot operate on a closed database.`

## Root cause
Two-layer chain:
1. **Direct bug**: `report_margin_balance()` in `daily_morning_report_v7.py` had:
   ```python
   if not rows:
       conn.close()          # BUG: closes the SHARED conn passed in from build_report()
       lines.append("> ❌ 无两融余额数据\n")
       return ...
   ```
   The function receives `conn` from `build_report()` (single connection reused across all modules). `close_conn` flag was only set True when the function created its own connection, but the `if not rows` branch closed the shared connection unconditionally. Next module `report_market_temperature(conn=conn)` then used the closed connection → "Cannot operate on a closed database."
2. **Trigger**: 两融 data source lagged — `margin_balance` max date was 20260806 (missing 08-07 & 08-10). Morning report queried the latest trade date (20260807) → no rows → hit the buggy branch.

## Fix
Remove the unconditional `conn.close()`; rely on the `finally` block which only closes when `close_conn` is True (i.e. connection was self-created):
```python
if not rows:
    lines.append("> ❌ 无两融余额数据\n")
    return "\n".join(lines) + "\n"
```
Pattern: helper functions taking optional `conn=None` must NEVER close an externally-passed connection. Only close connections they created themselves (`close_conn` flag).

## Debugging path (reusable)
1. **Check cron status ≠ check data**. `last_status: ok` in cron list only means exit 0. no_agent scripts can exit 0 while writing nothing, or write fine while a consumer breaks. Verify the actual DB rows: `SELECT MAX(trade_date) FROM <table>`.
2. **Check downstream consumers**. When a data-producing cron looks fine but the user reports a "failed" metric, check the consumer (morning report, web UI, other scripts), not just the producer. Morning report output lives at `~/.hermes/cron/output/3cb6fbcc8dcc/<date>.md`.
3. **Reproduce with a small harness** before/after the fix:
   ```bash
   ~/.hermes/venv_cron/bin/python3 -c "
   import sys; sys.path.insert(0, '.'); import daily_morning_report_v7 as m
   import sqlite3
   conn = sqlite3.connect(m.DB_PATH)
   out1 = m.report_margin_balance('20260807', conn=conn)   # no-data branch
   conn.execute('SELECT 1')   # must still work → connection NOT closed
   out2 = m.report_market_temperature(conn=conn, target_date='2026-08-10')
   print('OK' if '❌' not in out2 else 'FAIL')
   conn.close()"
   ```
   Also test `conn=None` self-created path to confirm `finally` close still fires.

## Related pitfall
- Data source lag (两融/板块流 trailing 1-2 days) is a data-source property, not a pipeline failure. Report scripts should handle no-rows gracefully (they do after the fix); the no-data branch is a normal path, not an error path.
