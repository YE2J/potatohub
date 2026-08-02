# Moneyflow Pipeline Audit — Real-World Example

## Scope

Audited `daily_moneyflow_tushare_dc.sh/py` (Tushare DC moneyflow) against reference pipeline `qfq_tushare_daily.sh/py` (Tushare QFQ daily kline).

## Technique: Pipeline Sibling Comparison

Instead of auditing a single pipeline in isolation, compare it against a **reference pipeline** that:
- Writes to the same database
- Uses the same API provider (Tushare)
- Has the same operator patterns (shell wrapper → Python → SQLite)
- Is already known to work correctly

Inconsistencies between the two reveal defects that neither pipeline would show alone.

## Key Findings

### 🔴 PK Without data_source → Data Loss

| Pipeline | PK |
|----------|----|
| moneyflow_daily table | `(stock_code, date)` — **missing data_source** |
| INSERT mode | `INSERT OR REPLACE` — replaces entire row |

When two pipelines write the same stock+date, the second run **silently overwrites** the first's data including the `data_source` tag. 4 data sources exist in this table (eastmoney, ths, ths_snapshot, tushare_dc).

### 🟡 Trade Calendar: API vs Local Table

| Pipeline | Date Resolution |
|----------|----------------|
| **qfq** | `get_latest_trade_date()` → check local `trade_cal` table first → fallback to `pro.trade_cal()` API |
| **moneyflow** | Always calls `pro.trade_cal()` API, hardcodes `start_date="20260101"` |

### 🔴 Shell Wrapper: Pre-flight Checks

| Check | qfq | moneyflow |
|-------|-----|-----------|
| `[ ! -f "$SCRIPT" ]` guard | ✅ Yes | ❌ Missing |
| `|| true` on pipe (pipefail safety) | ✅ Yes | ❌ Missing |

### 🟡 Field Redundancy

`net_amount` from API written to **both** `main_net_amt` and `net_mf_amt` — always identical, one column redundant.

### 🟡 Anti-Pattern: Dead Code

`CONFIRM_TIME = (17, 0)` defined but never referenced.  
`strip_ts_suffix()` defined but never called.

### 🟡 Anti-Pattern: Low Data-Ready Threshold

`has_data_for_date()` returns True at ≥100 rows (2% of market).  
qfq uses 4800 (96% of market). Partial write → date skipped forever.

### 🟡 Single Retry Without Backoff

30s sleep → one retry → hard fail. No exponential backoff.

## Process Summary

1. Read all 4 files (2 pipelines × .sh + .py)
2. Read DB schema (`PRAGMA table_info`, `PRAGMA index_list`, actual schema SQL)
3. Sample data for field semantics (verified `buy_elg_amount` is actually net)
4. Compare each check dimension between the two pipelines
5. Rate by severity: 🔴 (immediate risk), 🟡 (should fix), 🟢 (suggestion)
