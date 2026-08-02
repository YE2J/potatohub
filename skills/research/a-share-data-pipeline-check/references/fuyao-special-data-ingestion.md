# Fuyao Special-Data Ingestion Pipeline

Five special-data tables sourced from the Financial-API (fuyao) REST service into `stock_data.db`.

## Pipeline Overview

| Table | Endpoint | Collection | Cadence |
|-------|----------|-----------|---------|
| `limit_up_pool` | `limit-up-pool` | Daily after close | T+1 |
| `limit_up_ladder` | `limit-up-ladder` | Daily after close (30d window, no date parameter) | T+1 |
| `daily_anomaly` | `anomaly-analysis-list` | Real-time during trading hours | Same-day only (no history) |
| `dragon_tiger_daily` | `dragon-tiger-list` | Daily after close | T+1 |
| `hot_stock_daily` | `hot-stock-list` | Daily/hourly + real-time heat data | T+1/day period |

## Script

```bash
# Path
~/my_quant_system/scripts/import_financial_api.py

# Python (Hermes venv has incompatible urllib3 → must use pyenv Python)
PY=~/.pyenv/versions/3.11.11/bin/python

# Single table
export FUYAO_TOKEN="sk-fuyao-..."
$PY ~/my_quant_system/scripts/import_financial_api.py --table hot_stock_daily

# All tables
$PY ~/my_quant_system/scripts/import_financial_api.py --all

# With date
$PY ~/my_quant_system/scripts/import_financial_api.py --all --date 2026-07-03
```

## Table Schemas

### limit_up_pool
| Column | Type | Source API Field |
|--------|------|-----------------|
| trade_date | TEXT | supplied as arg |
| thscode | TEXT | `thscode` |
| stock_name | TEXT | `name` |
| first_limit_time | TEXT | `limit_up_time` |
| last_limit_time | TEXT | `limit_up_time` |
| open_times | REAL | N/A (NULL) |
| limit_reason | TEXT | `limit_up_reason` |
| board_count | REAL | `continue_day_cnt` |
| turnover_rate | REAL | N/A |
| close_price | REAL | `last_price` |
| pct_chg | REAL | `price_change_ratio_pct` |
| amount | REAL | N/A |
| fd_amount | REAL | N/A |
| market_cap | REAL | N/A |

### limit_up_ladder
| Column | Type | Source |
|--------|------|--------|
| trade_date | TEXT | `item[].date` |
| board_nums | INTEGER | board level (2..7) |
| stock_count | INTEGER | len of board array |
| stock_list | TEXT | JSON string of board entries |

### daily_anomaly
| Column | Type | Source |
|--------|------|--------|
| trade_date | TEXT | supplied as arg |
| thscode | TEXT | `thscode` |
| stock_name | TEXT | `stock_name` |
| anomaly_tags | TEXT | `tag_name` or `keyword_list` JSON |
| price | REAL | N/A |
| pct_chg | REAL | N/A |
| trigger_time | TEXT | N/A |

**Note**: `anomaly-analysis-list` returns same-day data only (no date parameter). Returns 0 rows on weekends/holidays.

### dragon_tiger_daily
| Column | Type | Source |
|--------|------|--------|
| trade_date | TEXT | `trade_date` from response |
| thscode | TEXT | `stock_items[].thscode` / `hot_money_items[].rows[].thscode` |
| stock_name | TEXT | `name` |
| board_type | TEXT | `board_type` |
| reason | TEXT | `limit_reason` |
| close_price | REAL | N/A |
| pct_chg | REAL | `change` × 100 |
| turnover_rate | REAL | N/A |
| total_amount | REAL | `buy_value` (approximation) |
| buy_top_amount | REAL | `buy_value` |
| sell_top_amount | REAL | `sell_value` |
| net_amount | REAL | `net_value` |

### hot_stock_daily
| Column | Type | Source |
|--------|------|--------|
| trade_date | TEXT | supplied as arg |
| thscode | TEXT | `thscode` |
| stock_name | TEXT | `name` |
| rank | INTEGER | `rank` |
| rank_type | TEXT | "day" or "hour" |
| score | REAL | `heat` (string, parsed to float) |
| pct_chg | REAL | N/A |
| current_price | REAL | N/A |

## How It Works

The script uses `subprocess` to call the fuyao CLI (a Python tool), parses the JSON stdout, extracts items from the envelope `{timestamp, [pagination], item: [...]}`, flattens nested structures (ladder → board levels, dragon-tiger → stock_items + hot_money_items rows), and `INSERT OR REPLACE` batches into SQLite at 500-row intervals.

## Known Issues & Mitigations (from 2026-07-05 review)

### 🔴 Issue 1: `daily_anomaly` table schema mismatches API

The table was designed expecting `{price, pct_chg, trigger_time}` but the API `anomaly-analysis-list` actually returns `{stock_name, analysis_content, keyword_list, thscode, tag_name}`. Result: **0 rows ever inserted** because `price`, `pct_chg`, `trigger_time` are all mapped to `None` and `INSERT OR REPLACE` skips all-None rows? Actually the INSERT still runs (all rows have PK values), but the table is effectively empty of useful data.

**Fix**: Rebuild the table to match API schema. Include `analysis_content` and `keyword_list` columns. Drop `price`, `pct_chg`, `trigger_time` or mark them as nullable N/A fields.

### 🔴 Issue 2: `dragon_tiger_daily.total_amount` = `buy_top_amount` (same API field)

Both columns are mapped to `item.get('buy_value')` in the script. The DB has identical values for every row. The API likely returns `buy_value` as the total buy amount (which is also the top-5 buy sum), so these semantically different columns hold the same data.

**Fix**: Drop `total_amount` from the table if the API doesn't provide an independent total. Or leave it as a user-convenience alias but document that it's not independently sourced.

### 🔴 Issue 3: `limit_up_pool` has 5 always-NULL columns

`open_times`, `turnover_rate`, `amount`, `fd_amount`, `market_cap` are NULL for all 104 rows. The API **does** return `seal_money` and `max_seal_money` (the sorting options include `seal_money`), which could populate `fd_amount`, but the script doesn't map them.

**Fix**: Map `item.get('seal_money')` → `fd_amount`. The other 4 fields (open_times, turnover_rate, amount, market_cap) are genuinely absent from this API — leave NULL for now; they can be populated via JOIN with `daily_kline` if needed.

### 🔴 Issue 4: `hot_stock_daily.pct_chg` and `current_price` always NULL

The API `hot-stock-list` does not return price change or current price in its `item[]`. It returns `{thscode, name, rank, heat, rank_change, rank_trend}`.

**Fix**: Either (a) drop these columns from the table, or (b) populate them via a post-hoc JOIN with `daily_kline` on the same trade_date.

### 🟡 Issue 5: Stock code format mismatch with watchlist

Watchlist stores bare codes (`301338`), while all fuyao tables use thscodes with suffixes (`301338.SZ`). This prevents direct JOIN and makes it impossible to filter "self-selected stocks only" without a format conversion step.

**Fix**: In the import script, add a `--watchlist-only` flag that reads watchlist, adds `.SH`/`.SZ`/`.BJ` suffix per exchange rules, then filters the API results. Or add a canonical `stock_code` column (bare 6-digit) alongside `thscode` in each table.

### 🟡 Issue 6: `--all` mode aborts on first failure

If one table's API call fails during `--all`, the script calls `sys.exit()` and remaining tables are skipped. Should use try/except + continue with error counters.

### 🟡 Issue 7: CLI parameter documentation drift

The plan document (and some reader assumptions) reference `--date` as a universal parameter. Reality:
| Command | Actual Args |
|---------|-------------|
| `limit-up-pool` | `--date-ms` (millisecond timestamp, not `--date`) |
| `limit-up-ladder` | No args |
| `anomaly-analysis-list` | `--tag-codes` (optional) |
| `anomaly-analysis-stock` | `--thscodes` or `--thscodes-file` |
| `dragon-tiger-list` | `--board-type` and `--date` (YYYY-MM-DD) |
| `hot-stock-list` | `--period day\|hour` |
| `skyrocket-list` | `--period day\|hour` |

### 🟢 Issue 8: No retry mechanism

API calls use `subprocess.run(timeout=60)` with zero retries. Network blips cause full-table failure.

### 🟢 Issue 9: No etl_runs logging

Unlike the Tushare pipelines, this script does not write to the `etl_runs` table. Cannot track freshness or execution history.

### 🟢 Issue 10: No cron shell wrappers

The plan's cron YAML references `daily_limit_up_fuyao.sh` etc., but no shell wrappers exist yet in `~/.hermes/scripts/`.

## Environment

```bash
export FUYAO_TOKEN="sk-fuyao-..."    # Required
```

The token is documented in `~/my_quant_system/financial-api/toolkit/fuyao/`. The fuyao script path is:
`~/my_quant_system/financial-api/toolkit/fuyao/scripts/fuyao.py`
