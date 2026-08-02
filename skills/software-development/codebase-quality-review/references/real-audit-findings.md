# Real Audit Findings Reference

This file documents concrete findings from a production codebase audit of `~/my_quant_system` (2026-07-02). Use these as pattern-matching templates when auditing other systems.

## Finding 1: Date Format Merge Failure

**Pattern:** Two databases with incompatible date string formats silently produce zero-match merges.

**Source A** (daily_kline table, populated by fast_download.py):
```python
# fast_download.py line 65 — strips dashes for storage
rows.append({"date": str(k[0]).replace("-",""), ...})
# → stores "20260630" (YYYYMMDD, no dashes)
```

**Source B** (daily_factors table, DDL-defined):
```sql
trade_date TEXT NOT NULL -- YYYY-MM-DD (with dashes)
```

**Merge point** (backtest_v4.py lines 560-562):
```python
# df['date'] from dz_dailyquote → "2026-06-30"  (dashes present)
# df['date'] from daily_kline fallback → "20260630"  (dashes stripped)
# f_df['date'] always from daily_factors → "2026-06-30"  (dashes present)
df = df.merge(f_df[['date', 'zhuli_holding', ...]], on='date', how='left')
```

**Consequence:** When load_to_dataframe falls back from dz_dailyquote to daily_kline, merge produces 0 matches → all factor columns are NaN → defaults trigger → wrong results.

**Detection:** After every pandas merge on date, assert minimum match rate:
```python
match_rate = df['zhuli_holding'].notna().sum() / len(df)
assert match_rate > 0.8, f"Merge date mismatch: only {match_rate:.1%} matched"
```

## Finding 2: Default Values That Bypass Conditions

**Pattern:** `fillna()` values chosen to make boolean checks pass, hiding missing data.

```python
# backtest_v4.py lines 565-572 — ALL defaults make conditions pass
df['zhuli_holding'] = df['zhuli_holding'].fillna(100.0)           # > 20 → TRUE
df['dark_pool_inflow_signal'] = df['dark_pool_inflow_signal'].fillna(1.0)  # == 1 → TRUE
df['prev_inflow'] = df['prev_inflow'].fillna(1.0)                  # == 1 → TRUE
```

**The signal path:**
- Condition requires `zhuli_holding > 20` → default is 100.0 → ALWAYS passes
- Condition requires `inflow == 1` → default is 1 → ALWAYS passes
- When data is missing, 2 of 4 buy conditions silently pass by default

**Correct alternatives:**
```python
# Conservative: data missing → condition fails
df['zhuli_holding'] = df['zhuli_holding'].fillna(0)     # fails > 20 check
df['inflow_signal'] = df['inflow_signal'].fillna(0)     # fails == 1 check

# Blocker: data missing → raise
if df['zhuli_holding'].isna().sum() > 0.5 * len(df):
    raise DataQualityError(f"zhuli_holding coverage only {(~df['zhuli_holding'].isna()).mean():.0%}")
```

## Finding 3: Hardcoded Data Windows in Fallback Path

**Pattern:** A "fallback" code path uses hardcoded dates while the primary path computes them dynamically.

```python
# screen_v4.py screen_fallback() — hardcoded
WHERE stock_code=? AND date>=? AND date<=?
→ params=(inner, "2026-01-01", date)      # ← HARDCODED

WHERE stock_code=? AND ... date>=? AND date<=?
→ params=(secu, "2026-05-01", date)       # ← HARDCODED
```

**Primary path uses:**
```python
# factors.py batch_load_data — dynamic
start_date = (pd.Timestamp(target_date) - pd.Timedelta(days=130)).strftime("%Y-%m-%d")
```

**Risk:** For recursive/recurrence indicators (zhuli_holding, macd, etc.), different lookback windows produce different values. A 130-day window vs 210-day window gives materially different zhuli_holding after accumulation.

**Rule:** `recursive_indicators["lookback_days"]` should be a single config const, not hardcoded differently in each path.

## Finding 4: Config Drift (Declared vs Consumed)

**Pattern:** Configuration dict defines keys that runtime code never reads.

```python
# config.py V4_PARAMS — 15 keys declared
V4_PARAMS = {
    "version": "v4.1.0",
    "max_positions": 3,
    "position_frac": 1/3,
    "buy_gs_g_or_bull": True,          # ← NEVER consumed by backtest_v4.py
    "buy_zhuli_cross_zero": True,      # ← NEVER consumed
    "buy_zhuli_holding_min": 20,       # ← NEVER consumed
    "sell_zhuli_consecutive_days": 3,  # ← NEVER consumed
    # ... 4 more sell/profit params also unused
}
```

**Meanwhile in backtest_v4.py:**
```python
# All these values are HARDCODED in the function body
max_positions: int = 3,
position_frac: float = 1/3,
# generate_signals() uses literal thresholds like zhuli_holding > 20
```

**Detection:** Cross-reference `grep "V4_PARAMS\["` against `grep -r "\"key_name\"" config.py`. Keys not consumed AND not protected by a deprecation comment are dead config.

## Finding 5: Missing Cron Wrapper Script

**Pattern:** A cron job references a file that doesn't exist.

```bash
# hermes cron list output:
# 273ca85e858c  [active]
#     Name:      因子回填-历史全量
#     Script:    backfill_cron.sh    # ← FILE DOES NOT EXIST
```

**Detection:**
```bash
find / -name "backfill_cron.sh" 2>/dev/null
# → empty result = task will run and immediately fail silently
```

**Fix:** Create the wrapper or update the cron job to point to the real script.

## Finding 6: Shell Script Without Error Detection

**Pattern:** A cron shell script that prints success messages unconditionally.

```bash
#!/bin/bash
cd ~/my_quant_system
~/.pyenv/versions/3.11.11/bin/python3 scripts/import_daily_factors.py daily --date "$TODAY" 2>&1
echo "[DONE] $TODAY"   # ← Always prints "[DONE]" even if python crashed
```

**Correct pattern:**
```bash
#!/bin/bash
set -euo pipefail
cd ~/my_quant_system
~/.pyenv/versions/3.11.11/bin/python3 scripts/import_daily_factors.py daily --date "$TODAY" 2>&1
rc=$?
if [ $rc -ne 0 ]; then
    echo "[FAIL] $TODAY (exit $rc)" >&2
    exit $rc
fi
echo "[DONE] $TODAY"
```

## Finding 7: Un-nulled Signals in In-Memory Computation

**Pattern:** A reusable generate_signals function assumes all columns exist, but when a data source is missing the columns, defaults silently substitute.

```python
# backtest_v4.py generate_signals lines 49-51
zhuli_holding = result.get("zhuli_holding", pd.Series([100.0] * n))
dark_pool_inflow = result.get("dark_pool_inflow_signal", pd.Series([1] * n))
prev_inflow = result.get("prev_inflow", pd.Series([1] * n))
```

When the upstream merge fails (see Finding 1), these defaults kick in.

**Defensive pattern:**
```python
# Check coverage before generating signals
expected_cols = ['zhuli_holding', 'dark_pool_inflow_signal', 'prev_inflow']
for col in expected_cols:
    if col not in result.columns or result[col].isna().all():
        raise ValueError(f"Column '{col}' missing or all-NaN — data coverage issue: {result[col].isna().sum()}/{len(result)} rows missing")
```
