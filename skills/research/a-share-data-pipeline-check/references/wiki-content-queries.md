# Wiki Content Generation — SQL Patterns

Use these queries when generating wiki content (每日盘面, 资金流追踪, etc.) from `stock_data.db`.

## 1. Index Cumulative Returns (N-Day Window)

For weekly/monthly performance tables comparing multiple indexes across rolling days:

```python
# Get last N days of index closes for cumulative returns
import sqlite3
conn = sqlite3.connect('~/my_quant_system/stock_data.db')
c = conn.cursor()

# Five major indexes
indexes = ['000001.SH', '000300.SH', '000688.SH', '399001.SZ', '399006.SZ']

# Get closes for the latest N days
c.execute('''
    SELECT ts_code, trade_date, close, pct_chg 
    FROM index_daily 
    WHERE ts_code IN ({}) 
      AND trade_date >= ?
    ORDER BY trade_date, ts_code
'''.format(','.join('?' * len(indexes))), 
    indexes + [cutoff_date_yyyymmdd])

# Group by trade_date in code, build cumulative return per index
# pct_chg is daily return already (not close-pct change)
```

**Format note**: `index_daily.trade_date` is **`YYYY-MM-DD`** (string, verified
2026-08-08 — `WHERE trade_date='2026-08-07'` returns 5 rows). The "YYYYMMDD"
claim in older versions of this note was WRONG. `market_moneyflow.trade_date`
IS `YYYYMMDD` — do not conflate the two. Compare with `>=`/`<=` string bounds.

## 2. Moneyflow Top-N with Watchlist Join

For 资金流追踪 pages: get top inflows/outflows limited to watchlist stocks:

```python
# Get watchlist mapping
c.execute('SELECT stock_code, stock_name FROM watchlist')
wl = {r[0]: r[1] for r in c.fetchall()}
codes = list(wl.keys())

# Watchlist-filtered top inflows on latest date
c.execute(f'''
    SELECT m.stock_code, w.stock_name, m.net_mf_amt 
    FROM moneyflow_daily m 
    JOIN watchlist w ON m.stock_code = w.stock_code
    WHERE m.date = ? AND m.net_mf_amt IS NOT NULL
    ORDER BY m.net_mf_amt DESC
    LIMIT 5
''', (latest_date,))

# Watchlist-filtered top outflows
c.execute(f'''
    SELECT m.stock_code, w.stock_name, m.net_mf_amt 
    FROM moneyflow_daily m 
    JOIN watchlist w ON m.stock_code = w.stock_code
    WHERE m.date = ? AND m.net_mf_amt IS NOT NULL
    ORDER BY m.net_mf_amt ASC
    LIMIT 5
''', (latest_date,))
```

## 3. Full-Market Moneyflow Aggregate

For the "全市场净额" summary line in daily reports:

```python
c.execute('''
    SELECT COUNT(*), 
           SUM(CASE WHEN net_mf_amt > 0 THEN 1 ELSE 0 END) AS inflow_count,
           SUM(CASE WHEN net_mf_amt < 0 THEN 1 ELSE 0 END) AS outflow_count,
           ROUND(SUM(net_mf_amt), 1) AS total_net
    FROM moneyflow_daily 
    WHERE date = ? AND data_source = 'tushare_dc'
''', (latest_date,))

# Format: f'{total_net/1e8:+.0f}亿'
```

### Inflow/Outflow Totals Breakdown

When writing daily reports, include separate inflow and outflow totals alongside the net:

```python
c.execute('''
    SELECT ROUND(SUM(CASE WHEN net_mf_amt > 0 THEN net_mf_amt ELSE 0 END) / 1e8, 2) AS inflow_亿,
           ROUND(SUM(CASE WHEN net_mf_amt < 0 THEN net_mf_amt ELSE 0 END) / 1e8, 2) AS outflow_亿,
           ROUND(SUM(net_mf_amt) / 1e8, 2) AS net_亿
    FROM moneyflow_daily 
    WHERE date = ? AND data_source = 'tushare_dc' AND net_mf_amt IS NOT NULL
''', (latest_date,))
```

This gives the inflow side (+833亿) and outflow side (-723亿) separately, not just the net (+110亿). Useful for showing the scale of activity behind the net number.

## 4. Limit-Up Pool Detail

For 涨停/异动 sections:

```python
# Latest date
c.execute('SELECT MAX(trade_date) FROM limit_up_pool')
pool_date = c.fetchone()[0]

# Total count
c.execute('SELECT COUNT(*) FROM limit_up_pool WHERE trade_date = ?', (pool_date,))
pool_count = c.fetchone()[0]

# Top stocks by board_count
c.execute('''
    SELECT stock_name, close_price, board_count, first_limit_time 
    FROM limit_up_pool 
    WHERE trade_date = ? 
    ORDER BY board_count DESC 
    LIMIT 10
''', (pool_date,))
```

## 5. Market Moneyflow (大盘资金流)

```python
# Latest market-level data
c.execute('''
    SELECT trade_date, sh_close, sh_pct_change, main_net_inflow 
    FROM market_moneyflow 
    ORDER BY trade_date DESC 
    LIMIT 2
''')

# Format: main_net_inflow in yuan -> divide by 1e8 for 亿
```

`market_moneyflow.trade_date` is `YYYYMMDD` format (no dashes). `sh_pct_change` is a percentage value (e.g. `1.65` for +1.65%).

## 6. Dragon Tiger & Anomaly Stats

```python
c.execute('SELECT MAX(trade_date), COUNT(*) FROM dragon_tiger_daily')
dt_date, dt_count = c.fetchone()

c.execute('SELECT MAX(trade_date), COUNT(*) FROM daily_anomaly')
an_date, an_count = c.fetchone()

# Dragon tiger top by net amount
c.execute('''
    SELECT stock_name, buy_top_amount, sell_top_amount, reason 
    FROM dragon_tiger_daily 
    WHERE trade_date = ? 
    ORDER BY buy_top_amount DESC 
    LIMIT 3
''', (dt_date,))
```

## 7. Limit-Up Ladder (连板天梯)

```python
c.execute('''
    SELECT board_nums, stock_count 
    FROM limit_up_ladder 
    WHERE trade_date = ? 
    ORDER BY board_nums ASC
''', (ladder_date,))
```

## 8. Full-Market Moneyflow Top-N (Unfiltered)

For the "全市场 Top5" tables:

```python
# Market-wide top inflows
c.execute('''
    SELECT m.stock_code, m.net_mf_amt 
    FROM moneyflow_daily m 
    WHERE m.date = ? AND m.net_mf_amt IS NOT NULL 
    ORDER BY m.net_mf_amt DESC 
    LIMIT 5
''', (latest_date,))

# Market-wide top outflows  
c.execute('''
    SELECT m.stock_code, m.net_mf_amt 
    FROM moneyflow_daily m 
    WHERE m.date = ? AND m.net_mf_amt IS NOT NULL 
    ORDER BY m.net_mf_amt ASC 
    LIMIT 5
''', (latest_date,))
```

Stock names are NOT in `moneyflow_daily` — you need to join with `watchlist` or `daily_kline` to get names. Use `watchlist.stock_name` for self-selected stocks. For non-watchlist stocks, a fallback lookup from `daily_kline` via stock_code works.

## 9. K-Line Date Distribution Check

When the `MAX(date)` returns a date that seems old, check both date formats:

```python
c.execute("SELECT MAX(date), COUNT(*) FROM daily_kline WHERE length(date) = 10")
# YYYY-MM-DD format (active pipeline)

c.execute("SELECT MAX(date), COUNT(*) FROM daily_kline WHERE length(date) = 8")  
# YYYYMMDD format (legacy watchlist, may be stale)
```

## Common Pitfalls

1. **Units**: `net_mf_amt` in `moneyflow_daily` is in **yuan**, not 万 or 亿. Divide by 1e8 for 亿 display.
- `market_moneyflow.trade_date` = `YYYYMMDD`. Always verify with `PRAGMA table_info` and sample data.
- **`sector_moneyflow_dc.trade_date`** = `YYYYMMDD` (no dashes). This is different from `moneyflow_daily.date` which is `YYYY-MM-DD`. Always check the format before cross-joining.
3. **NULL values**: `net_mf_amt` can be NULL even when the row exists. Filter with `IS NOT NULL`.
4. **Stock codes**: `moneyflow_daily` uses stock_code (e.g. `603986`) without exchange suffix. `watchlist` also uses bare stock_code. No `.SH`/`.SZ` suffix needed.
5. **Watchlist tables**: `watchlist` has `stock_code` and `stock_name` columns. Group is in `group_name` (e.g. '默认自选', '0616_光纤光缆').
6. **⭐ Moneyflow `data_source` filter**: `moneyflow_daily` has a `data_source` column. The active incremental pipeline writes `'tushare_dc'`. Queries without `WHERE data_source='tushare_dc'` may return stale rows from other sources or composite data. All moneyflow queries in this reference should filter by data_source. **Example (section 3 corrected):**
   ```sql
   SELECT COUNT(*),
          SUM(CASE WHEN net_mf_amt > 0 THEN 1 ELSE 0 END) AS inflow_count,
          SUM(CASE WHEN net_mf_amt < 0 THEN 1 ELSE 0 END) AS outflow_count,
          ROUND(SUM(net_mf_amt), 1) AS total_net
   FROM moneyflow_daily
   WHERE date = ? AND data_source = 'tushare_dc';
   ```
7. **⭐ `limit_up_pool` = 涨停 only (no 跌停)**: The `limit_up_pool` table has no `limit_type` column — every row is a 涨停 record. There is NO 跌停 counterpart in this table. The name `limit_up_pool` is literal. For 跌停 counts, use the `limit_up_list` data source (Tushare `limit_list` API) or the `kpl_list` (开盘啦) table if available.
8. **⭐ `dragon_tiger_daily` column names**: The columns are `buy_top_amount` and `sell_top_amount` (not `buy_amount`/`sell_amount`). Stock name is in `stock_name`. Query pattern:
   ```sql
   SELECT stock_name, buy_top_amount, sell_top_amount, reason
   FROM dragon_tiger_daily
   WHERE trade_date = ?
   ORDER BY buy_top_amount DESC LIMIT 5;
   ```
9. **Cron mode query alternative**: When running as a cron job (`execute_code` blocked), use `terminal` + `sqlite3` with `.schema` discovery first:
   ```bash
   # Discover columns before querying an unfamiliar table
   sqlite3 ~/my_quant_system/stock_data.db ".schema moneyflow_daily" | head -5
   
   # Query with date param (use single quotes for SQL strings)
   sqlite3 ~/my_quant_system/stock_data.db "
     SELECT stock_code, ROUND(net_mf_amt/1e8,2) || '亿' as net
     FROM moneyflow_daily
     WHERE date='2026-07-13' AND data_source='tushare_dc'
     ORDER BY ABS(net_mf_amt) DESC LIMIT 10;
   "
   ```
   Union queries in `sqlite3` must use `UNION ALL` and each SELECT is independent. Only the last failing query causes a non-zero exit.

## 10. Hot Stock Daily (市场热榜)

```bash
# Schema
sqlite3 ~/my_quant_system/stock_data.db ".schema hot_stock_daily"
```

Columns: `trade_date, thscode, stock_name, rank, rank_type, score, pct_chg, current_price`. No `amount` column — the table stores ranking metadata, not trade volumes.

```python
# Latest date and count
c.execute('SELECT MAX(trade_date) FROM hot_stock_daily')
c.execute('SELECT COUNT(*) FROM hot_stock_daily WHERE trade_date = ?', (latest,))

# Top ranked stocks on a given date
c.execute('''
    SELECT stock_name, rank, pct_chg, score
    FROM hot_stock_daily
    WHERE trade_date = ? AND rank_type = 'hot'
    ORDER BY rank ASC LIMIT 10
''', (latest,))
```

## 11. K-Line Average Stats by Date

For the 每日盘面 "全市场平均涨幅" summary:

```bash
sqlite3 ~/my_quant_system/stock_data.db "
    SELECT COUNT(*) as cnt,
           ROUND(AVG(pct_change), 2) as avg_pct,
           ROUND(AVG(amount/1e8), 2) as avg_amt_亿
    FROM daily_kline
    WHERE date = '2026-07-14' AND length(date) = 10;
"
```

The `length(date)=10` filter excludes legacy YYYYMMDD rows. Note: `AVG()` in SQLite auto-silences NULLs — if pct_change is NULL for a row, it's simply not counted in the average, not treated as 0. This is correct behavior for this query. If the result seems wrong (e.g. avg_pct = 1.51 on a down day), verify against a single stock sample:

```bash
# Spot-check
sqlite3 ~/my_quant_system/stock_data.db "
    SELECT stock_code, pct_change, close
    FROM daily_kline
    WHERE date = '2026-07-14' AND length(date) = 10
    ORDER BY RANDOM() LIMIT 5;
"
```

## 12. Self-Join for Stock Names (moneyflow + daily_kline)

`moneyflow_daily` has no stock name column directly. To get names in cron mode (no Python pandas joins available):

```bash
# Join moneyflow with daily_kline for stock names on a specific date
sqlite3 ~/my_quant_system/stock_data.db "
    SELECT mf.stock_code, kl.name, ROUND(mf.net_mf_amt/1e8,2) as net_yi
    FROM moneyflow_daily mf
    JOIN (
        SELECT DISTINCT stock_code, name FROM daily_kline WHERE date='<YYYY-MM-DD>'
    ) kl ON mf.stock_code = kl.stock_code
    WHERE mf.date='<YYYY-MM-DD>' AND mf.net_mf_amt IS NOT NULL
    ORDER BY mf.net_mf_amt DESC LIMIT 10;
"
```

If the JOIN returns empty, the `daily_kline.name` column may be named differently (check with `.schema daily_kline`).

## 13. `main_net_amt` NULL Fallback Pattern

⚠️ **Critical:** In `moneyflow_daily`, `main_net_amt` can be **100% NULL for all rows on a given date**, even though `net_mf_amt` has fully populated data. This happens when the data source provides net moneyflow but not the breakdown.

```bash
# Quick health check: is main_net_amt usable?
sqlite3 ~/my_quant_system/stock_data.db "
    SELECT COUNT(*) as total,
           SUM(CASE WHEN main_net_amt IS NOT NULL THEN 1 ELSE 0 END) as filled,
           SUM(CASE WHEN net_mf_amt IS NOT NULL THEN 1 ELSE 0 END) as net_filled
    FROM moneyflow_daily WHERE date='<YYYY-MM-DD>';
"

# If main_net_amt filled = 0 but net_filled > 0, fallback to net_mf_amt:
sqlite3 ~/my_quant_system/stock_data.db "
    SELECT stock_code, ROUND(net_mf_amt/1e8,2) as net_yi
    FROM moneyflow_daily
    WHERE date='<YYYY-MM-DD>' AND net_mf_amt IS NOT NULL
    ORDER BY net_mf_amt ASC LIMIT 10;
"
```

**Rule**: Always verify the column you plan to use has real data. Don't assume `main_net_amt DESC` returned valid values just because it returned rows.

## 14. Stock Name Lookup via stock_name_map

`moneyflow_daily` has no stock name column. Instead of joining with `daily_kline` (section 12), use the simpler `stock_name_map` table:

```bash
sqlite3 ~/my_quant_system/stock_data.db "
    SELECT stock_code, stock_name
    FROM stock_name_map
    WHERE stock_code IN ('000063','002156','601899','603993','603893');
"
```

**Schema:** `stock_code TEXT (PK), stock_name TEXT, source TEXT DEFAULT 'ths'`
**Coverage:** Includes all common A-share codes. No exchange suffix needed.
**Trade-off:** Only has stock name, no price data. Use daily_kline join when you need both name and price.

## 15. Valuation Results Queries

For updating the 估值动态 wiki page, query `valuation_results`:

### Latest Batch Detection (prefer run_id over run_date)

```bash
# Get the latest run_id and associated data
sqlite3 ~/my_quant_system/stock_data.db "
    SELECT MAX(run_id) as latest_run, COUNT(*) as count
    FROM valuation_results
    WHERE run_id = (SELECT MAX(run_id) FROM valuation_results);
"

# Latest batch detail
sqlite3 ~/my_quant_system/stock_data.db "
    SELECT stock_code, stock_name, data_as_of,
           ROUND(safety_margin*100,0) as margin_pct, rating
    FROM valuation_results
    WHERE run_id = (SELECT MAX(run_id) FROM valuation_results)
    ORDER BY ABS(safety_margin) DESC LIMIT 10;
"
```

**Key columns:**
- `run_id` (INTEGER) — batch identifier, always use `MAX(run_id)` for latest
- `data_as_of` (DATE) — the data cutoff date (not `run_date`!)
- `run_date` (DATETIME) — when the batch ran, auto-set to CURRENT_TIMESTAMP
- `safety_margin` (REAL) — decimal, ×100 for %. Positive ≈ undervalued
- `rating` (TEXT) — '显著低估','低估','偏低','中性','偏高','高估','显著高估'
- `primary_model` / `model_version` — model tracking

⚠️ **`data_as_of` vs `run_date` nuance:** `data_as_of` is the effective data date (e.g., '2026-06-17' for the last full weekly batch). `run_date` is when the batch was computed. For wiki staleness tracking, use `data_as_of`. For pipeline health, use `run_date`.

### Distribution by Rating

```bash
sqlite3 ~/my_quant_system/stock_data.db "
    SELECT rating, COUNT(*) as cnt
    FROM valuation_results
    WHERE run_id = (SELECT MAX(run_id) FROM valuation_results)
    GROUP BY rating ORDER BY cnt DESC;
"
```

## 16. Cron Output Directory Layout

When the daily wiki update needs to find morning reports or check cron outputs, use this pattern:

```bash
# All cron output lives under job-ID directories
~/.hermes/cron/output/
├── <job_id_1>/          # e.g., 3cb6fbcc8dcc = 每日晨报采集
│   └── YYYY-MM-DD_HH-MM-SS.md
├── <job_id_2>/          # dc4d14272d63 = 每日DB备份
└── ...

# Find the most recent output across all jobs
find ~/.hermes/cron/output/ -name "*.md" -mtime -1 2>/dev/null | sort

# Key cron job IDs:
# 3cb6fbcc8dcc = 每日晨报采集 (07:05)
# dc4d14272d63 = 每日DB备份 (03:03)
# baab58cec144 = DNS缓存更新 (00:00)
# 910124571b2d = 资金流向-Tushare-DC增量 (18:30)
# 263ec7d6d324 = 每日因子更新 (19:00)
# 82d135d6a369 = Wiki增量整理 (03:30)
# 62f94e3b9c5a = 板块轮动 (20:00, script failed)

# Alternative: query cron_push_log for recent job activity
sqlite3 ~/my_quant_system/stock_data.db "
    SELECT job_name, status, finished_time, duration_ms
    FROM cron_push_log
    ORDER BY id DESC LIMIT 10;
"
```

**`cron_push_log` schema:** id, job_name, job_id, scheduled_time, actual_time, finished_time, status, duration_ms, exit_code, content_path, content_size, log_tail

## 17. Extreme Day / Crash Reporting

When reporting a significant down day (index decline >3% or moneyflow <-800亿):

### Record-Breaking Declarations

Explicitly flag records with markdown emphasis:

```markdown
| Metric | Value | Status |
|--------|-------|--------|
| 科创50 single-day | -7.12% | 💥 **Largest this month** |
| 全市场净流出 | -1,571亿 | 💥 **Cron-record largest** |
| 上证 3800 | 3764 | 🔴 **Breached!** |
```

### Key Level Analysis After Support Breach

Show the trail from prior support levels:

```python
sh_close = 3764.15
print(f"上证 from 3850(3月前低): {(3850/sh_close - 1)*100:.1f}% below")
star_close = 1715.40
peak = 2185
retrace = (peak - star_close) / peak * 100
print(f"科创50 from {peak}高点: 回撤 {retrace:.1f}% — {'技术性熊市' if retrace > 20 else '深度回调'}")
```

### Weekly Summary From Cumulative Data

When a calendar week completes, assemble full-week performance:

```python
c.execute('''
    SELECT ts_code, trade_date, ROUND(close,2), ROUND(pct_chg,2)
    FROM index_daily
    WHERE trade_date >= ? AND trade_date <= ?
      AND ts_code IN ('000001.SH','000300.SH','000688.SH','399001.SZ','399006.SZ')
    ORDER BY ts_code, trade_date
''', (mon_yyyymmdd, fri_yyyymmdd))

# Compounding: (1+r1/100)*(1+r2/100)*...*(1+r5/100) - 1
cumulative = {}
for code, date, close, pct in rows:
    if code not in cumulative:
        cumulative[code] = 1.0
    cumulative[code] *= (1 + pct/100)
# cumulative = {code: week_return_percent} already
```

### Moneyflow Evolution Table (W-N format)

For weeks with extreme flows, build a day-by-day comparison:

```bash
sqlite3 ~/my_quant_system/stock_data.db "
    SELECT date, ROUND(SUM(net_mf_amt)/1e8,2) as total
    FROM moneyflow_daily
    WHERE date BETWEEN '2026-07-13' AND '2026-07-17' AND data_source='tushare_dc'
    GROUP BY date ORDER BY date;
"
```

Then format into a table showing daily total and the single largest outflow/inflow stock per day (queried separately per date).
