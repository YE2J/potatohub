# Fuyao Special-Data Ingestion Pipeline

Seven special-data tables sourced from the Financial-API (fuyao) REST service into `stock_data.db`.

## Pipeline Overview

| Table | Endpoint | Collection | Cadence |
|-------|----------|-----------|---------|
| `limit_up_pool` | `limit-up-pool` | Daily after close | T+1 |
| `limit_up_ladder` | `limit-up-ladder` | Daily after close (30d window, no date parameter) | T+1 |
| `limit_down_pool` | `limit-down-pool` | Daily after close | T+1 |
| `limit_break_pool` | `limit-break-pool` | Daily after close | T+1 |
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

### limit_down_pool
| Column | Type | Source API Field |
|--------|------|-----------------|
| trade_date | TEXT | supplied as arg |
| thscode | TEXT | `thscode` |
| stock_name | TEXT | `name` |
| last_price | REAL | `last_price` |
| pct_chg | REAL | `price_change_ratio_pct` |
| first_limit_time | TEXT | `first_limit_time` (HH:mm) |
| last_limit_time | TEXT | `last_limit_time` (HH:mm) |
| turnover_rate | REAL | `turnover_ratio_pct` |

### limit_break_pool
| Column | Type | Source API Field |
|--------|------|-----------------|
| trade_date | TEXT | supplied as arg |
| thscode | TEXT | `thscode` |
| stock_name | TEXT | `name` |
| last_price | REAL | `last_price` |
| pct_chg | REAL | `price_change_ratio_pct` |
| open_times | INTEGER | `open_times` (开板次数) |
| turnover_rate | REAL | `turnover_ratio_pct` |
| turnover | REAL | `turnover` (成交额, 元) |

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
| thscode | TEXT | `stock_items[].thscode` |
| stock_name | TEXT | `name` |
| board_type | TEXT | `board_type` (历史恒 'all') |
| reason | TEXT | `limit_reason` |
| close_price | REAL | N/A |
| pct_chg | REAL | `change` × 100 |
| turnover_rate | REAL | N/A |
| buy_top_amount | REAL | `buy_value` |
| sell_top_amount | REAL | `sell_value` |
| net_amount | REAL | `net_value` |

> ⚠️ 采集语义（实测 2026-09-08）：collector 硬编码 `--board-type all`；all 响应 `hot_money_items` **恒为空**（游资明细仅在独立 `board_type=hot_money` 榜返回），故历史 46 日 3054 行全部来自 `stock_items`。同股同榜同日可多行且无记录 ID → `PRIMARY KEY(trade_date, thscode)` 已静默覆盖重复行（如 9/2 丢 5 股重复），按 board_type 分榜明细应另建表用 DELETE+INSERT，勿原地改此表。

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

## Adding a New Fuyao Endpoint to This Pipeline (4-layer recipe)

1. **fuyao_client.py** — add typed function (sort-field whitelist constants + `_get` call).
2. **fuyao.py CLI** — import the function, add `cmd_*` handler, add `sub.add_parser` with `--date-ms`/`--page`/`--size`/`--sort-field`/`--sort-dir`.
3. **import_financial_api.py** — add `_collect_*` (pagination loop size 200; date→`date_ms` 上海零点毫秒), add `TABLE_SPEC` entry (`INSERT OR REPLACE`), bump docstring/`--help` table counts (5→7 etc.).
4. **DB + cron** — `CREATE TABLE` (PRIMARY KEY(trade_date, thscode) if genuinely unique-per-day-per-code, else DELETE+INSERT), shell wrapper in `~/.hermes/scripts/daily_*_fuyao.sh` with `cron_log_init` using the **real cron job id** (create cron first, then fill id — a placeholder id makes cron logs orphaned), register no_agent cron job.

Verification before cron: real single-day fetch (`--date` historical day with known data) → row count > 0; re-run same day → count unchanged (idempotent). Never conclude "endpoint broken" from one 0-row day — probe a historical date with known data first.

## Known Issues & Mitigations (from 2026-07-05 review)

### 🔴 Issue 1: `daily_anomaly` table schema mismatches API

The table was designed expecting `{price, pct_chg, trigger_time}` but the API `anomaly-analysis-list` actually returns `{stock_name, analysis_content, keyword_list, thscode, tag_name}`. Result: **0 rows ever inserted** because `price`, `pct_chg`, `trigger_time` are all mapped to `None` and `INSERT OR REPLACE` skips all-None rows? Actually the INSERT still runs (all rows have PK values), but the table is effectively empty of useful data.

**Fix**: Rebuild the table to match API schema. Include `analysis_content` and `keyword_list` columns. Drop `price`, `pct_chg`, `trigger_time` or mark them as nullable N/A fields.

### ✅ Issue 2 (RESOLVED): `dragon_tiger_daily.total_amount` = `buy_top_amount` (same API field)

Both columns were mapped to `item.get('buy_value')` in the script. The `total_amount` column has been **dropped from the DB** (`fix_db_schema.py` S2) — current schema has no `total_amount`; keep it that way when touching the table.

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

### ✅ Issue 10 (RESOLVED): cron shell wrappers exist and are scheduled

Wrappers live in `~/.hermes/scripts/daily_*_fuyao.sh` and run as daily `*‑FinancialAPI` cron jobs (see SKILL.md table for schedule/job mapping). Each wrapper sources `~/.hermes/.env.fuyao`, runs `~/.hermes/venv_cron/bin/python3 scripts/import_financial_api.py --table <t> --date <YYYY-MM-DD>` from `~/my_quant_system`, and uses `cron_log_helper.sh` for delivery.

## API integration facts (verified 2026-09-08)

| Item | Value |
|------|-------|
| Base URL | `https://fuyao.aicubes.cn` (`fuyao_client.py` `BASE_URL`) |
| Auth header | **`X-api-key: <token>`** — Bearer is rejected with `code 2003 Missing X-api-key` |
| Token | `~/.hermes/.env.fuyao` → `FUYAO_TOKEN` (client also accepts `API_KEY`) |
| Rate limit | HTTP 429 body `{"code":429,"request limit exceeded"}`; transient — `fuyao_client._get` retries with backoff (RETRY_CODES {4001,5001,5002,5003}, max 3, base 1s) → cron self-heals |

Diagnostic note: a bare `curl` probe that returns 429 twice in quick succession is rate limiting, not an outage; wait, then retry with the `X-api-key` header.

## Environment

```bash
export FUYAO_TOKEN="sk-fuyao-..."    # Required
```

Cron path uses `~/.hermes/venv_cron/bin/python3` (the historical pyenv/urllib3 incompatibility no longer applies to the wrapper path). Token documented in `~/my_quant_system/financial-api/toolkit/fuyao/`; fuyao CLI at `~/my_quant_system/financial-api/toolkit/fuyao/scripts/fuyao.py`.

---

> **2026-09-08 更新注**：fuyao 文档站已扩版至 **34 REST 参考页 / 58 MCP 工具**（2026-09-08，此前本地镜像滞后停在 Jul 4 的 23/22）。本文件描述的 5 表管线（limit_up_pool / limit_up_ladder / daily_anomaly / dragon_tiger_daily / hot_stock_daily）与端点**仍有效**，不受扩版影响；新增端点（炸板池 limit-break-pool、跌停池 limit-down-pool、龙虎榜分榜 board_type=org/hot_money、集合竞价 auction/*、估值 valuations/*、基金 fund/*）的完整契约与端点地图见 skill **`fuyao-a-share-api`**（`~/.hermes/skills/research/fuyao-a-share-api/references/endpoints-map.md`，权威字段级契约 = `~/my_quant_system/financial-api/toolkit/fuyao/docs/llms-full.txt`）。
> ⚠️ 龙虎榜注意：`dragon_tiger_daily` 历史全 `board_type='all'`（all=机构+游资合并口径，非 org/hot_money 分榜），任何按 board_type 的过滤需知此语义；分榜明细另建表（2026-09-08 起）。

