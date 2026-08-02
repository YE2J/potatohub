# Worked Example: Financial-API → SQLite Data Integration Plan Review

> Date: 2026-07-05
> Plan: `~/my_quant_system/docs/financial-api-integration.md`
> Script: `~/my_quant_system/scripts/import_financial_api.py`
> DB: `~/my_quant_system/stock_data.db` (6.9 GB)
> API CLI: `~/my_quant_system/financial-api/toolkit/fuyao/scripts/fuyao.py`

## Summary

5 tables created (limit_up_pool, limit_up_ladder, daily_anomaly, dragon_tiger_daily, hot_stock_daily). All had data. But 4 critical field-mapping errors caused widespread NULL values.

## Investigation Steps

### Step 1: Read Plan
- 8 sections: data source mapping, table schemas, update strategy, cron plan, priority tiers
- Priority: 🔴 high → 🟡 medium → 🟢 low

### Step 2: Check DB Against Plan
```python
# For each target table:
cur.execute("PRAGMA table_info(tablename)")
# Compare column names, types, PKs against plan's DDL
```
Result: All 5 tables existed with matching columns.

### Step 3: Check Script Against Plan
- Script's SQL INSERT column lists matched plan's DDL
- CLI arguments in script: verify against actual `argparse` definitions

### Step 4: Check Script Against API (Most Important)
Read the actual CLI source (`fuyao.py` + `fuyao_client.py`):

```bash
# Find CLI argument definitions
grep -n 'add_argument\|def cmd_*' fuyao.py
# Find API response field names
grep -n 'def special_data_' fuyao_client.py
```

Key discoveries:
| Script says | API actually returns | Issue |
|-------------|---------------------|-------|
| `item.get('price')` → `None` | No `price` field | Wrong field |
| `item.get('pct_chg')` → `None` | No `pct_chg` field | Wrong field |
| `item.get('buy_value')` → both `total_amount` and `buy_top_amount` | Only one `buy_value` field | Copied to 2 columns |
| `item.get('seal_money')` not mapped | API returns `seal_money` | Missed opportunity |

### Step 5: Check Real DB Data Quality

```python
# Discover NULL rates per column
for tbl, cols in [('limit_up_pool', ['open_times','turnover_rate','amount','fd_amount','market_cap']),
                  ('dragon_tiger_daily', ['close_price','turnover_rate']),
                  ('hot_stock_daily', ['pct_chg','current_price'])]:
    null_cases = ' + '.join(...)
    cur.execute(f'SELECT trade_date, COUNT(*), {null_cases} FROM {tbl} GROUP BY trade_date')

# Spot-check semantic correctness
# dragon_tiger_daily: total_amount == buy_top_amount for every row → SAME FIELD in script
```

Result: 4 tables with widespread NULLs. `daily_anomaly` had 0 rows.

### Step 6: Assess Operational Readiness
- No retry mechanism in script
- `--all` mode exits on first failure (`sys.exit()`)
- No cron shell wrappers exist in `~/.hermes/scripts/`
- No `etl_runs` logging

### Step 7: Cross-Reference Stock Code Formats
```python
cur.execute('SELECT stock_code FROM watchlist')  # Returns: '301338' (bare)
cur.execute('SELECT thscode FROM limit_up_pool') # Returns: '301338.SZ' (suffixed)
```
Watchlist (154 stocks) uses bare 6-digit codes; all new tables use thscodes with `.SH`/`.SZ` suffix → **cannot JOIN directly**.

## Findings

| Severity | Finding | Root Cause |
|----------|---------|------------|
| 🔴 | `daily_anomaly` has 0 rows — table expects {price, pct_chg, trigger_time} but API returns {tag_name, keyword_list, analysis_content} | Table designed against assumed API contract, not verified API output |
| 🔴 | `dragon_tiger_daily.total_amount` == `buy_top_amount` (same API `buy_value` written to both columns) | Copy-paste error in script field mapping |
| 🔴 | 5 `limit_up_pool` columns always NULL; API's `seal_money` not mapped to `fd_amount` | Plan documented fields from Tushare mental model, not from actual API schema |
| 🔴 | `hot_stock_daily.pct_chg` and `current_price` always NULL | API doesn't return price fields; plan assumed they'd exist |
| 🟡 | Stock code format: watchlist bare vs thscode suffixed | No normalization layer in the plan |
| 🟡 | `--all` mode aborts on first table failure | No try/except around individual table collection |
| 🟢 | No retry, no cron wrappers, no etl_runs logging | Operational convenience not yet implemented |

## Priority Fixes

1. **Rebuild `daily_anomaly` DDL** to match API response (drop `price`/`pct_chg`/`trigger_time`, add `keywords`/`analysis_content`)
2. **Fix `dragon_tiger_daily` mapping** — remove duplicate `total_amount` or source it from a different API field
3. **Map `seal_money`** → `fd_amount` in `_collect_limit_up_pool()`
4. **Add `--watchlist-only`** flag with bare-code → thscode suffix conversion
5. **Make `--all` resilient** — individual table failures should not abort remaining tables
