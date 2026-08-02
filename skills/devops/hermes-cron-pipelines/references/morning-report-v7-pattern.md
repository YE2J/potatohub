# 晨报 v7 — Weekday-Aware + Simplified Weekend Reports

## Architecture (v7.0, 2026-07-27)

```
07:05 → cron runs daily_morning_report_v7.py (no_agent=true via shell wrapper)
       → script detects datetime.now().weekday()
       → Mon(0): simplified report + 上周资金流入TOP
       → Sun(6): simplified report + 本周总结
       → Tue~Sat: full normal report
       → stdout = complete report → cron delivers via deliver=all
```

**Key changes from v6:**
- v6: Agent-driven cron (`no_agent=false`), every day identical output
- v7: no_agent script-driven, weekday-sensitive branching, simplified weekend mode

## Weekday Logic

| Day | `weekday()` | Mode | Extra modules |
|-----|:-----------:|------|:-------------:|
| Mon | 0 | Simplified | `📊 上周资金流入TOP` |
| Tue | 1 | Full | — |
| Wed | 2 | Full | — |
| Thu | 3 | Full | — |
| Fri | 4 | Full | — |
| Sat | 5 | Full | — |
| Sun | 6 | Simplified | `📅 本周总结` |

**Simplified mode:** Skips detailed TOP5 moneyflow tables, margin balance breakdown, and market temperature analysis. Shows only:
- Date stamp + "数据最新来自 **{date}**，与上次晨报相同"
- Simplified moneyflow: just `📅 {date} | 数据源: DC`
- Simplified margin: `> 全市场两融余额: **{num}亿**`
- Simplified temperature: `> {icon} 最新温度: **{t}** (label) {action}`
- Plus the extra module (weekly top sectors or weekly summary)

## Extra Module: 上周资金流入TOP (Monday)

```python
def report_weekly_top_sectors(conn, last_trade_date):
    """Aggregate the last 5 trading days' sector moneyflow."""
    trading_days = get_recent_trading_days(conn, 5, end_date=last_trade_date)
    # For each sector: sum(net_amount) across 5 days → rank → top5
    # For each industry: same
    # Mark 🔥 重点关注 if:
    #   cumulative > 1e9 * len(trading_days)    (avg >= 10亿/day)
    #   AND top5_appearances >= max(2, len(trading_days) - 1)
```

**Dynamic threshold rationale:** Hardcoded thresholds (e.g. >50亿 and >=3 days) break during holiday-shortened weeks. The dynamic version scales with actual trading days.

## Extra Module: 本周总结 (Sunday)

```python
def report_weekly_summary(conn, last_trade_date):
    """Three sub-sections aggregated from last 5 trading days."""
    # 1) 大盘温度趋势 — daily temp table with week-over-week delta
    # 2) 本周各日资金流入TOP1概念 — daily top earner
    # 3) 本周累计净流入 TOP3 — aggregate
    # 4) 两融趋势 — week-start vs week-end comparison
```

**Pitfall — date format mismatch:** `market_temperature.trade_date` is `YYYY-MM-DD` but `sector_moneyflow_dc.trade_date` and `trade_cal.cal_date` are `YYYYMMDD`. When querying market_temperature from trading_days, convert: `temp_days = [f"{d[:4]}-{d[4:6]}-{d[6:]}" for d in trading_days]`.

## no_agent Shell Wrapper

```bash
# ~/.hermes/scripts/daily_morning_report_v7.sh
PYTHON="$HOME/.pyenv/versions/3.11.11/bin/python3"
SCRIPT="$SCRIPT_DIR/daily_morning_report_v7.py"

# DB 可用性检查（外置盘休眠保护）
if ! timeout 3 sqlite3 "$DB_PATH" "SELECT 1;" >/dev/null 2>&1; then
    LATEST_BACKUP=$(ls -t "$DB_FALLBACK_DIR"/stock_data_*.db | head -1)
    cp "$LATEST_BACKUP" /tmp/stock_data_morning.db
    export MORNING_DB_PATH="/tmp/stock_data_morning.db"
fi

OUTPUT=$("$PYTHON" "$SCRIPT" 2>&1)
echo "$OUTPUT"
```

**Python path note:** `~/.pyenv/versions/3.11.11/bin/python3` fails in terminal (TCC blocks Homebrew gettext) but works under launchd (scheduled cron). Alternative `~/.local/bin/python3.11` works in terminal for basic Python ops but cannot access `/Volumes/*/` external drives. For cron, use pyenv path — it gets full filesystem access via launchd.

**DB env var:** Python script's `DB_PATH` now reads `os.environ.get("MORNING_DB_PATH") or os.path.expanduser("...")` — the shell wrapper can redirect the database to a local backup copy when the external disk is asleep.

## Cron Integration

```
Schedule: 5 7 * * *       (daily, 07:05)
Mode: no_agent=true
Script: daily_morning_report_v7.sh
Deliver: all
Prompt: "[SILENT]-aware, passes through script output verbatim"
```

## Migration Path

| Step | What | Why |
|:----:|------|-----|
| 1 | Create v7.py with weekday branching | Add `report_weekly_top_sectors()` and `report_weekly_summary()` functions |
| 2 | MOA multi-model review | 5 models cross-validate code quality, SQL injection, edge cases |
| 3 | Fix P0-P2 issues | Date format conversion, placeholders scope, dynamic thresholds |
| 4 | Create no_agent shell wrapper | Bypass agent TCC sandbox for /Volumes/ DB access |
| 5 | Switch cron to no_agent=true | Test scheduled run via launchd (not manual trigger) |
| 6 | Update cron prompt | Add [SILENT] handling, remove agent-level commentary |

## File Locations

```
~/.hermes/scripts/daily_morning_report_v7.py    — Python script (~1050 lines)
~/.hermes/scripts/daily_morning_report_v7.sh    — no_agent shell wrapper
~/.hermes/cron/output/3cb6fbcc8dcc/             — cron output directory
```

## Key Pitfalls Found in Review

| # | Pitfall | Fix |
|:-:|---------|-----|
| 1 | `market_temperature.trade_date` is `YYYY-MM-DD` vs other tables `YYYYMMDD` | Convert trading_days before querying temperature table |
| 2 | `placeholders` defined inside try block — industry query references it from outer scope | Move `placeholders = ','.join(...)` before the try |
| 3 | `is_data_unchanged()` defined but never called | Integrate into `build_report()` for accurate stale-data messaging |
| 4 | Hardcoded thresholds (5亿, 3天) broken for holiday weeks | Dynamic: `min_days=max(2,N-1)`, `threshold=1e9*N` |
| 5 | `report_margin_balance()` opens separate DB connection each call | Accept optional `conn` parameter for reuse |
| 6 | Manual cron trigger inherits terminal TCC sandbox — always test via scheduled run | Document launchd vs terminal distinction |
| 7 | External disk sleep → sqlite3 hangs on 1st access via symlink | Add `timeout 3` probe + fallback to local backup in shell wrapper |
