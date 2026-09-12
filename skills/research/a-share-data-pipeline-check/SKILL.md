---
name: a-share-data-pipeline-check
description: "Query stock_data.db SQLite database to check freshness of all data pipelines (kline, moneyflow, index, valuation), run watchlist moneyflow analysis, and produce data health reports."
version: 2.2.0
tags: [a-share, data-pipeline, sqlite, moneyflow, kline, valuation, quant-system]
---

# A-Share Data Pipeline Status Check

Check the health of all data pipelines in the quant system (`~/my_quant_system/stock_data.db`).

## Key Insight: Independent Freshness

**Critical pattern:** Each data source has INDEPENDENT freshness. Never assume correlation:
- `index_daily` may be fresh through Friday while `daily_kline` is stuck at Wednesday
- `moneyflow_daily` may resume production while `daily_kline` remains stuck
- `valuation_results` has its own cron and fails independently
- **Cron jobs can silently NOT trigger** — a missing day in the DB doesn't always mean a pipeline failure; the cron scheduler may have simply not fired

Always query ALL sources and build a freshness matrix.

## Pipeline → Cron Job Mapping

| Table | Cron Name | Script | Schedule | Delivery |
|-------|-----------|--------|----------|----------|
| `daily_kline` | 前复权日线-Tushare增量 | `qfq_tushare_daily.sh` | 18:00 交易日 | local |
| `moneyflow_daily` | 资金流向-Tushare-DC增量 | `daily_moneyflow_tushare_dc.sh` | 18:30 交易日 | local |
| `index_daily` | 指数日线-Tushare增量 | `daily_index_tushare.sh` | 18:15 交易日 | local |
| `valuation_results` | (weekly_valuation agent) | — | Sat ~09:00 | local |

## Fuyao Special-Data Tables (同花顺金融数据 API = fuyao.aicubes.cn)

**Terminology gate:** when the user says「同花顺金融数据 API」they mean **fuyao.aicubes.cn** (同花顺官方数据服务, repo `~/my_quant_system/financial-api/`), NOT the Tushare `moneyflow_ind_ths/cnt_ths` 板块资金流口径. Both coexist; confirm which one is meant before diagnosing or the whole investigation targets the wrong source.

Seven tables from the Financial-API (fuyao) special-data endpoints. Each has a **daily cron wrapper** (`~/.hermes/scripts/daily_*_fuyao.sh` → `import_financial_api.py --table <t> --date <YYYY-MM-DD>`, venv_cron Python, token from `~/.hermes/.env.fuyao`):

| Table | Cron (name / wrapper) | Schedule | Endpoint |
|-------|-----------------------|----------|----------|
| `limit_up_pool` | 涨跌停池-FinancialAPI / `daily_limit_up_fuyao.sh` | 交易日 16:00 | `limit-up-pool` |
| `limit_up_ladder` | 连板天梯-FinancialAPI / `daily_limit_up_ladder.sh` | 交易日 16:05 | `limit-up-ladder` |
| `limit_down_pool` | 炸板跌停池-FinancialAPI / `daily_limit_break_down_fuyao.sh` | 交易日 16:10 | `limit-down-pool` |
| `limit_break_pool` | 炸板跌停池-FinancialAPI / `daily_limit_break_down_fuyao.sh` | 交易日 16:10 | `limit-break-pool` |
| `daily_anomaly` | 个股异动-FinancialAPI / `daily_anomaly_fuyao.sh` | 交易日 15:30 | `anomaly-analysis-list` |
| `dragon_tiger_daily` | 龙虎榜-FinancialAPI / `daily_dragon_tiger_fuyao.sh` | 交易日 17:00 | `dragon-tiger-list` |
| `hot_stock_daily` | 市场热榜-FinancialAPI / `daily_hot_stock_fuyao.sh` | 交易日 22:00 | `hot-stock-list` |

**当日 0 行 ≠ 端点故障或非交易日**（判别法）：①历史日回查（已知有数据的日期逐日拉，如跌停池 9/7=2、9/4=9、9/2=8）②兄弟端点对照（同日涨停池有 N 行证明日期语义对）。跌停/炸板这类情绪池当日真实可为 0（无跌停/无炸板是合法结果），别把合法空日当故障排查。

**dragon-tiger-list 三榜不同构（实测）**：all/org 榜返回股级 `stock_items`（org 含 org_net_value/org_buy_num/org_sell_num 机构字段），`hot_money_items` 恒为空；hot_money 榜反之 `stock_items` 空、`hot_money_items`=[{name, buying, rows:[游资×股]}]。同股同榜同日可多行且无记录 ID（仅 range_days 等不同）→ 该数据不能按 (trade_date, thscode) 唯一键落库否则静默丢行；逐日快照用 DELETE(trade_date, board_type)+全量 INSERT 幂等。三榜集合关系：org⊂all、hot_money 个股⊂all、org∩hot_money 部分重叠。

**API integration facts (verified 2026-09-08):** Base URL `https://fuyao.aicubes.cn`; auth header is **`X-api-key: <token>`** — `Authorization: Bearer` is rejected with `code 2003 Missing X-api-key`; token in `~/.hermes/.env.fuyao` (`FUYAO_TOKEN`, alias `API_KEY`). HTTP **429 "request limit exceeded"** is transient rate limiting — `fuyao_client.py _get` auto-retries with backoff (RETRY_CODES {4001,5001,5002,5003}, max 3, base 1s), so a 429 line in a cron log followed by a write is healthy, not a failure.

**Cron `ok` ≠ rows written**: verify fuyao health by reading the cron output md (`~/.hermes/cron/output/<job_id>/<date>.md`) for the trailing write count (e.g. `✅ 写入 231 条`) or by DB `MAX(trade_date)` / row count per table, not by `last_status`.

Full schema, per-endpoint CLI args, and historical issues: [references/fuyao-special-data-ingestion.md](references/fuyao-special-data-ingestion.md)

## Database Location

```bash
DB=~/my_quant_system/stock_data.db
```

## Core Tables and Their Freshness

| Table | Freshness Column | Format | Expected Cadence | Pipeline |
|-------|-----------------|--------|-----------------|----------|
| `daily_kline` | `date` | `YYYY-MM-DD` (varchar) | T+1 daily ~18:00 | 前复权日线-Tushare增量 |
| `index_daily` | `trade_date` | `YYYY-MM-DD` (str) | T+1 daily ~18:15 | 指数日线-Tushare增量 |
| `moneyflow_daily` | `date` | `YYYY-MM-DD` (str) | T+1 daily ~18:30 | 资金流向-Tushare-DC增量 |
| `sector_moneyflow_dc` | `trade_date` | `YYYYMMDD` (int) | T+1 daily ~18:45 | 板块资金流向-每日增量 |
| `sector_moneyflow_ths` | `trade_date` | `YYYYMMDD` (int) | T+1 daily ~18:45 | (same cron, THS source) |
| `valuation_results` | `run_date` | `YYYY-MM-DD` (str) | Weekly (Sat) | weekly_valuation |
| `margin_balance` | `trade_date` | `YYYYMMDD` (int) | T+1 daily ~18:35 (Mon–Fri only) | 两融余额 |
| `market_temperature` | `trade_date` | `YYYY-MM-DD` (str) | 交易日盘后 (L1 引擎) | 大盘温度 |
| `sector_rotation` | `trade_date` | `YYYY-MM-DD` (str) | 交易日盘后 (L2 引擎) | 板块轮动 |
| `decision_log` | `trade_date` | `YYYY-MM-DD` (str) | 交易日盘后 (L3 引擎) | 决策融合 |
| `daily_factors` | `trade_date` | `YYYY-MM-DD` (str) | T+1 daily | 每日因子更新 |
| `hot_stock_daily` | `trade_date` | `YYYY-MM-DD` (str) | 交易日 ~22:00 | 市场热榜 |
| `market_moneyflow` | `trade_date` | `YYYYMMDD` (int) | ⚠️ 无 cron（07-16 起停滞） | 大盘资金流 |

**Column-name trap (verified 2026-08-02)**: the freshness column is NOT uniform —
`daily_kline`/`moneyflow_daily` use `date`, `valuation_results` uses `run_date`, all
others use `trade_date`. `daily_kline` has NO `trade_date` column; `SELECT
MAX(trade_date) FROM daily_kline` fails with `no such column`. When in doubt, run
`PRAGMA table_info(<table>)` first. Formats also split by table: engine tables
(`market_temperature`/`sector_rotation`/`decision_log`/`daily_factors`/
`hot_stock_daily`) and `index_daily` store `YYYY-MM-DD`; balance/sector tables
(`margin_balance`/`sector_moneyflow_dc`/`sector_moneyflow_ths`/`market_moneyflow`)
store `YYYYMMDD`.

## Freshness Query Template

```python
import sqlite3
db = sqlite3.connect('stock_data.db')
c = db.cursor()

# Latest dates
c.execute('SELECT MAX(date) FROM daily_kline')
kline_date = c.fetchone()[0]
c.execute('SELECT COUNT(*) FROM daily_kline WHERE date = ?', (kline_date,))
kline_count = c.fetchone()[0]

c.execute('SELECT MAX(trade_date) FROM index_daily')
index_date = c.fetchone()[0]

c.execute('SELECT MAX(date) FROM moneyflow_daily')
mf_date = c.fetchone()[0]
c.execute('SELECT COUNT(*) FROM moneyflow_daily WHERE date = ?', (mf_date,))
mf_count = c.fetchone()[0]

c.execute('SELECT MAX(run_date) FROM valuation_results')
val_date = c.fetchone()[0]

db.close()

print(f'K线: {kline_date} ({kline_count}只)')
print(f'指数: {index_date}')
print(f'资金流: {mf_date} ({mf_count}只)')
print(f'估值: {val_date}')
```

## Watchlist Query

```python
c.execute('SELECT stock_code, stock_name, group_name FROM watchlist')
# groups: '默认自选', '0616_光纤光缆', '0617_国家大基金持股', etc.
```

## Moneyflow Top-N Analysis

### Full-market Top5 Outflows

```python
c.execute('''
SELECT stock_code, net_mf_amt FROM moneyflow_daily 
WHERE date = ? ORDER BY net_mf_amt ASC LIMIT 5
''', (date_str,))
```

### Full-market Top5 Inflows

```python
c.execute('''
SELECT stock_code, net_mf_amt FROM moneyflow_daily 
WHERE date = ? ORDER BY net_mf_amt DESC LIMIT 5
''', (date_str,))
```

### Watchlist Moneyflow (all stocks on a given date)

```python
c.execute('SELECT stock_code, stock_name FROM watchlist')
wl = {row[0]: row[1] for row in c.fetchall()}
codes = list(wl.keys())
placeholders = ','.join(['?'] * len(codes))

# Outflow top5
c.execute(f'''
SELECT stock_code, net_mf_amt, main_net_amt, lg_net_amt 
FROM moneyflow_daily WHERE date = ? AND stock_code IN ({placeholders})
ORDER BY net_mf_amt ASC
''', [date_str] + codes)

# Inflow top5: reverse the ORDER BY to DESC
```

### Date Coverage (detect gaps)

```python
c.execute('''
SELECT date, COUNT(*) FROM moneyflow_daily 
WHERE date >= ? GROUP BY date ORDER BY date
''', (cutoff_date,))
```

## Index Daily (Market Summary)

The five major indexes in `index_daily`:

| TS Code | Name |
|---------|------|
| 000001.SH | 上证指数 |
| 000300.SH | 沪深300 |
| 000688.SH | 科创50 |
| 399001.SZ | 深证成指 |
| 399006.SZ | 创业板指 |

```python
c.execute('''
SELECT trade_date, ts_code, close, pct_chg 
FROM index_daily WHERE trade_date >= ? 
ORDER BY trade_date, ts_code
''', (cutoff_date,))
```

## Data Integrity Verification

### Expected Row Counts

| Table | Normal Full-Market Count | Notes |
|-------|-------------------------|-------|
| `daily_kline` | ~5,100–5,200 | Standard A-stock listing codes only |
| `moneyflow_daily` | ~5,000–5,200 | Varies by date; narrower than kline |
| `index_daily` | 5 rows/date | 5 major indexes only |

### Detecting Anomalies

**Counting per date** is the first check when investigating gaps:

```python
for d in candidate_dates:
    cnt = conn.execute("SELECT COUNT(*) FROM daily_kline WHERE date=?", (d,)).fetchone()[0]
    print(f'{d}: {cnt}条')
```

**Anomaly signals:**
- **0 rows** on a confirmed trading day → pipeline never ran for that date (check cron logs)
- **1–4,999 rows** on `daily_kline` (expected ~5,100–5,200) → **partial write** — the script crashed mid-way while writing via `INSERT OR REPLACE`. Cron output will show `script failed` but the DB still has partial data.
- **>6,000 rows** → may include non-standard codes (old delisted stocks like `10000`, `10036`), indicates a manual backfill or broader stock_basic query
- **~10,000+ rows** → double coverage of non-standard codes, not necessarily corrupt data but worth noting

**Confirming a trading day** (don't assume holidays):

```python
# Preferred: query local trade_cal table (populated from Tushare, synced weekly)
conn.execute("SELECT cal_date, is_open FROM trade_cal WHERE exchange='SSE' AND cal_date=?", (date_str,)).fetchone()

# Fallback: Via Tushare trade_cal MCP
# mcp_tushareMcp_trade_cal(exchange='SSE', start_date='...', end_date='...')
```

### Trade Calendar Table

The `trade_cal` table in `stock_data.db` stores A-share trading calendars for SSE and SZSE exchanges:

| Column | Type | Description |
|--------|------|-------------|
| `exchange` | TEXT | `SSE` or `SZSE` |
| `cal_date` | TEXT | `YYYYMMDD` format |
| `is_open` | INTEGER | `1` = trading day, `0` = closed |
| `pretrade_date` | TEXT | Previous trading day |

- **Coverage**: 1990-12 ~ present
- **Sync**: Weekly cron `交易日历-Tushare同步` (Mon 10:00)
- **When checking `is_open`**: Note `is_open` is INTEGER, not TEXT. Compare as `is_open=1` not `is_open='1'`. SQLite auto-coerces but explicit integer comparison is cleaner.
- **Usage query**: `SELECT MAX(cal_date) FROM trade_cal WHERE exchange='SSE' AND is_open=1 AND cal_date <= ?` to find the latest trading day
- **⚠️ CRITICAL PITFALL**: `get_latest_trade_date()` in both `qfq_tushare_daily.py` and `daily_moneyflow_tushare_dc.py` MUST call Tushare API directly, NOT query the local `trade_cal` table. The trade_cal sync cron runs weekly (Mon 10:00). By Thu/Fri the local table is 2-4 trading days behind, but the query STILL succeeds (returns last cached date), so the API fallback never fires. Result: pipelines silently skip all new data. **Fix: always use `pro.trade_cal()` API for the latest date, skip the local cache entirely** (applied 2026-07-09).

### ⚠️ CRITICAL PITFALLS

#### Dual Date Formats in daily_kline

The `daily_kline` table has TWO distinct date formats producing DRAMATICALLY different results:

| Format | Example | Stocks/Date | Scope | Status |
|--------|---------|-------------|-------|--------|
| `YYYYMMDD` (no dashes, len=8) | `20260626` | ~147 | Watchlist only (default自选) | ⛔ Stale |
| `YYYY-MM-DD` (with dashes, len=10) | `2026-07-06` | ~5,000+ | Full market subset | 🟢 Active |

**Why this matters**: `SELECT MAX(date) FROM daily_kline` returns `20260626` (the old format's latest date), NOT the actual latest data at `2026-07-06`. This can make the entire pipeline appear "stuck" for days when it's actually updating normally.

**Always check BOTH formats when assessing freshness:**

```python
# Chcek old format
c.execute("SELECT MAX(date) FROM daily_kline WHERE length(date)=8")
old_max = c.fetchone()[0]
c.execute("SELECT COUNT(*) FROM daily_kline WHERE date=?", (old_max,))
old_cnt = c.fetchone()[0]

# Check new format  
c.execute("SELECT MAX(date) FROM daily_kline WHERE length(date)=10")
new_max = c.fetchone()[0]
c.execute("SELECT COUNT(*) FROM daily_kline WHERE date=?", (new_max,))
new_cnt = c.fetchone()[0]

print(f"Old format (YYYYMMDD): {old_max} ({old_cnt}只) — watchlist only")
print(f"New format (YYYY-MM-DD): {new_max} ({new_cnt}只) — full market")
```

**Root cause**: The kline pipeline changed its date format at some point. The old format rows (~147 stocks) are a legacy watchlist subset that stopped updating. The new format rows (~5,000 stocks) are the active pipeline. 
**Do NOT rely on `MAX(date)` alone** — always inspect the date format distribution.

#### Confirming Trading Days: Don't Guess

**Never assume a date is a non-trading day based on its name or holiday reputation.** Always verify against the official calendar:

```python
# Query the local trade_cal table
c.execute("SELECT is_open FROM trade_cal WHERE exchange='SSE' AND cal_date=?", (date_str,))
result = c.fetchone()
is_trading_day = result[0] == 1 if result else False
```

**Real-world example**: 2026-07-01 was initially reported as "香港回归纪念日, non-trading day" in wiki logs, but the SSE `trade_cal` confirmed `is_open=1` — it was a normal trading day. The moneyflow cron did miss that day, but that's a pipeline gap, not a holiday.

#### 0 Rows ≠ Pipeline Failure for New-Format Data

If `daily_kline` shows 0 rows for a date in the old format (`YYYYMMDD`), it may just mean the old format isn't being populated anymore. Check the new format before concluding the pipeline is broken:
```python
c.execute("SELECT COUNT(*) FROM daily_kline WHERE date=? AND length(date)=10", (target_date,))
```

### Disk I/O Error — SQLite Cannot Open Database

When `sqlite3` returns `Error: in prepare, disk I/O error (10)` or `unable to open database file (14)`:

**Immediate diagnosis:**
```bash
df -h /
# If "Available" is <500 MB on a multi-GB DB, the disk is too full
```

#### Symlink → External Drive (TCC) — Same Error, Different Cause

**First check whether `stock_data.db` is a symlink before assuming disk-full:**

```bash
ls -la ~/my_quant_system/stock_data.db
# ENTITY FILE (healthy):  -rw-r--r--@ 1 yellow staff 6941253632 Aug  1 03:02 stock_data.db
# SYMLINK (TCC risk):     lrwxr-xr-x@ 1 yellow staff 33 Jul 27 22:10 stock_data.db -> /Volumes/500gb/data/stock_data.db
stat /Volumes/500gb/data/stock_data.db
# TCC denial shows: "stat: ...: Operation not permitted" or sqlite3 "authorization denied"
```

**Root cause**: macOS TCC session lock denies the external volume when the screen is locked / machine idle — `launchd` cron is ALSO denied (not configurable). Every script that opens the DB through the symlink crashes with `sqlite3.OperationalError: unable to open database file`, so 10-15 pipelines fail simultaneously even though `df` shows plenty of space and the external disk mounts fine.

**Diagnostic evidence**: the one-off diagnostic cron jobs print the DB linkage directly — read their latest output in `~/.hermes/cron/output/`:
- `47c218bf809d` 两融诊断 → prints `DB symlink:` line
- `da719983a44d` / `d207089fb8ce` 外置盘诊断/权限验证 → show `ls: /Volumes/500gb/: Operation not permitted` + sqlite3 `authorization denied`
- `badc7ef3c79c` 内置盘DB验证 → confirms entity file is queryable

**⚠️ Verify CURRENT state, don't trust memory or logs**: a "DB migrated to internal disk" note does NOT mean today's pipeline ran against it. Check the file's mtime vs the failure window — e.g. 2026-07-31: migration happened 23:14 but the 18:00–22:00 pipeline batch all failed because they still hit the symlink. `ls -la` + `stat` + file mtime are the ground truth.

**Resolution**: replace the symlink with a real file on the internal disk (the external volume stays as backup only). After migration, `sqlite3 stock_data.db "SELECT MAX(trade_date) FROM margin_balance;"` to confirm read-back, and `PRAGMA wal_checkpoint(TRUNCATE)` / `PRAGMA integrity_check` to verify.

**Diagnostic shortcut — simultaneous multi-pipeline failure:**
When 5+ different cron scripts (factor update, sector moneyflow, decision fusion, etc.) all fail simultaneously with `sqlite3.OperationalError: unable to open database file`, this is almost certainly an **external disk I/O issue**, not individual script bugs. The disk (external 500GB SSD via USB‑C) entered a slow-response state or timed out during the evening batch window (~18:00–20:30). Diagnosis:
- `df -h /` will show **free space is fine** (unlike disk-full scenario)
- The external disk's USB controller may have entered a power-save state
- Recovery: `diskutil eject` + re-mount, or wait for the next cron cycle
- **Do NOT** debug each script individually — file one issue for the disk I/O

**Partial write signature:** A script that starts writing via INSERT OR REPLACE but crashes mid-way leaves **partial data** in the DB. For daily_kline, a count of ~2,744 vs expected ~5,193 is diagnostic — the MAX(date) query returns the date (because at least one row was written), hiding the failure. **Always pair MAX(date) with COUNT(*) for that date.**

**Root cause:** SQLite needs free disk space for internal operations (WAL recovery, temp indices). When the disk is 100% full, SQLite returns opaque I/O errors on ANY query — including `SELECT MAX(...)`.

**Recovery (free space quickly):**
```bash
brew cleanup --prune=all       # ~300-500 MB
pip cache purge                # ~50-100 MB
npm cache clean --force        # ~50-100 MB
df -h /                        # verify recovery
```

**If DB remains inaccessible after cleanup**, it may be genuinely corrupted (rare — disk-full errors usually resolve after space is freed).

### When DB Cannot Be Queried: Fallback to Cron Output Files

When `stock_data.db` is inaccessible, use `~/.hermes/cron/output/` as fallback for confirming data collection.

```bash
# Key pipeline job IDs (from jobs.json):
#   0c029d10767b → 前复权日线 (K线)
#   910124571b2d → 资金流向DC
#   5575f1bae80e → 指数日线
#   263ec7d6d324 → 因子更新

# Read the latest output for a pipeline:
ls -t ~/.hermes/cron/output/0c029d10767b/ | head -1
# Look for lines like: "DONE: 2026-07-24 → 5197 只股票写入 daily_kline"
```

**Reporting fallback results:**
```
K线: 07-24 ✅ (Cron确认5,197只写入, DB暂不可查)
资金流: 07-24 ✅ (Cron确认5,834只写入, DB暂不可查)
```

### Database Recovery After Disk Full

After freeing space:
```bash
# 1. Try a simple query
sqlite3 ~/my_quant_system/stock_data.db "SELECT 1;"

# 2. Checkpoint the WAL
sqlite3 ~/my_quant_system/stock_data.db "PRAGMA wal_checkpoint(TRUNCATE);"

# 3. Run integrity check
sqlite3 ~/my_quant_system/stock_data.db "PRAGMA integrity_check;"
```

**Important:** Cron pipelines use `INSERT OR REPLACE` — data written before the crash is safe. Data in-flight during the crash may be missing but can be re-filled by re-running the cron (idempotent).

### Non-Standard Codes (the "doubling" phenomenon)

When historical backfill runs pull from `stock_basic` with a different filter than the incremental runs, old delisted codes (e.g. `10000`, `10017`, `10069`, `100636`) may appear. These inflate the row count but are valid `INSERT OR REPLACE` entries — no primary key violations. The incremental pipeline's `has_data_for_date()` uses GLOB patterns (`0[0-9][0-9][0-9][0-9][0-9]`, `3...`, `6...`, `8...`, `4...`) which match standard 6-digit codes, so the existence of non-standard codes does NOT cause a false-positive "data exists" check.

## Pipeline Troubleshooting

When a date has 0 rows but was a confirmed trading day:

### Step 1: Check CRON triggered

```bash
# List cron jobs to find the relevant job_id
cronjob action='list'

# Check whether the cron produced output for the target date
ls -la ~/.hermes/cron/output/<job_id>/
# If no output file exists for that date, the scheduler did NOT fire the job
```

### Step 2: Check script execution logs

```bash
# qfq_tushare_daily.sh logs to ~/.logs/qfq_tushare.log
grep "<target_date>" ~/.logs/qfq_tushare.log

# The log contains every run: both manual (with "手动模式") and cron ("增量模式")
# Search for [START] to see all runs
grep "\[START\]" ~/.logs/qfq_tushare.log
```

### Step 3: Manually backfill a missing date

```bash
bash ~/.hermes/scripts/qfq_tushare_daily.sh 20260701
```

The script auto-detects the latest trading day from Tushare and skips dates that already have >= 4800 rows in the DB. When given a date argument, it backfills that specific day.

### Step 4: Verify after backfill

```python
# Check row count after backfill
cnt = conn.execute("SELECT COUNT(*) FROM daily_kline WHERE date=?", (target_date,)).fetchone()[0]
print(f'{target_date}赛后: {cnt}条 (期望 ~5,100-5,200)')
```

### Known False Alarm: cron_log_helper integer comparison

When a `no_agent=true` script exits, you may see stderr like:
```
/Users/yellow/.hermes/scripts/cron_log_helper.sh: line 100: [: 17831258443N: integer expression expected
```

This is a **benign bug** in `cron_log_helper.sh` — the script appends `N` (for "new") to a number before comparing it as an integer. The data pipeline itself completed successfully. Distinguish this from a real failure by checking:
- The stdout contains `写入完成` / `DONE` — data was written
- The `exit_code` in the cron run is 1 (from the helper) but data exists in the DB
- The log file (`~/.logs/qfq_tushare.log`) shows the complete batch execution

### Cron Silent Failure Pattern

The cron scheduler may silently not trigger a job on a given day without recording an error. The only reliable way to detect this is:
1. Check `cronjob action='list'` — `last_run_at` will show the previous successful run
2. Check the cron output directory for the expected date
3. The `last_status` remains "ok" from the last successful run — there is no "never ran" state

## Reporting Convention

Use consistent format when reporting data freshness:

```
K线: <latest> ❌ 连续 <N> 个交易日缺失（<date_range>）
资金流: 🚀 最新 <latest> 全量 <N> 只到达！
估值: <latest> ❌ 停滞第 <N> 日，<cron_status>
指数: <latest> ✅ 五大指数均正常
```

Status emoji: 🚀 (new data), ✅ (stable), ⏸️ (paused), ❌ (failing/stale), 🟢/🟡/🔴 (traffic lights).

## Backfill After Mass Pipeline Failure (Manual Recovery)

When an evening batch fails (TCC symlink denial, migration completed too late, transient token errors, etc.), missing dates must be backfilled manually — pipelines do NOT auto-heal gaps. All scripts support idempotent manual backfill (`INSERT OR REPLACE`, safe to re-run):

| Data | Script | Backfill Command |
|------|--------|------------------|
| kline | `~/.hermes/scripts/qfq_tushare_daily.sh` | `bash qfq_tushare_daily.sh 20260731` |
| moneyflow | `~/.hermes/scripts/daily_moneyflow_tushare_dc.sh` | `bash daily_moneyflow_tushare_dc.sh 20260731` |
| index | `~/.hermes/scripts/daily_index_tushare.sh` | `bash daily_index_tushare.sh` (incremental auto-fills gaps; `--backfill` = full) |
| sector THS | `~/my_quant_system/scripts/daily_sector_moneyflow.py` | `~/.hermes/venv_cron/bin/python3 ... --date 20260731` |
| sector DC | `~/my_quant_system/scripts/daily_sector_moneyflow_dc.py` | `... --date 20260731` |
| margin | `~/.hermes/scripts/daily_margin_balance.sh` | `bash daily_margin_balance.sh` (auto from latest gap) |
| L1 大盘温度 | `~/my_quant_system/engines/market_temperature.py` | `venv_cron/bin/python3 engines/market_temperature.py --date 2026-07-31` |
| L2 板块轮动 | `~/my_quant_system/engines/sector_rotation.py` | `... --date 2026-07-31` |
| L3 决策融合 | `~/my_quant_system/engines/decision_fusion.py` | `... --date 2026-07-31` |

**Date formats**: kline/moneyflow/sector take `YYYYMMDD` (8-digit); engines take `--date` accepting `YYYY-MM-DD` or `YYYYMMDD`.

**Critical rules (pitfalls):**
1. **After backfilling data tables, MUST re-run L1→L2→L3 engines per date** (`--date` for each missing day) — data backfill does NOT trigger engine recompute; otherwise the morning report still shows "昨日无温度数据".
2. **margin is T+1 published**: backfilling the most recent trading day may write 0 rows — NORMAL, not a failure. The gap auto-fills on the next weekday 18:35 cron (margin cron only runs `35 18 * * 1-5`; Friday data backfilled on Saturday = 0 rows, wait for Monday).
3. **kline partial writes re-run fine**: `has_data_for_date()` skips only dates with >=4800 rows (STOCK_MIN_COUNT). A 2744-row partial write re-runs to full ~5197.
4. Parallelize kline/moneyflow in background (`terminal(background=true, notify_on_complete=true)`); run same-script dates serially. Source token first: `source ~/.hermes/.env.tushare; export TUSHARE_TOKEN`.
5. **Post-migration leftover cleanup**: `stock_data.db.real` (3.8G+), `stock_data_new.db*`, `stock_data.symlink_to_external.bak`, `stock_data.bak.db*` are all safe to delete after `lsof <file>` confirms no process holds them; keep external-disk `/Volumes/500gb/data/stock_data.db` as backup.

Full command matrix, verification queries, and the 2026-08-01 case study: [references/backfill-procedures.md](references/backfill-procedures.md)

## Known Data Gaps

- **Weekends**: Sat/Sun — no trading, all pipelines idle by definition
- **Holiday calendar**: Check via `mcp_tushareMcp_trade_cal(exchange='SSE')` if uncertain — do NOT assume holidays based on date name alone

## Column-Level Data Quality Checks

**Critical pattern**: A table may have rows for a date but the **actual data columns are NULL**. Never assume row presence = data availability. Always spot-check the data columns themselves.

### Moneyflow data: `main_net_amt` can be effectively empty (verified 2026-07-06)

`moneyflow_daily` may store dates from 2007 but the `main_net_amt` column may have only a handful of non-null rows (e.g. 5 out of 3,000+). This is a **data pipeline failure** — the ETL wrote date records but never populated the numeric values. Pattern across 20 case-study stocks: exactly **5 non-null rows** per stock, all from the very end of the date range (2026-06-29 ~ 2026-07-03). **This makes `main_net_amt`-derived factors (`main_net_ratio`, `main_net_amt_5d`) effectively unusable.**

Quick health check:
```sql
SELECT COUNT(*) AS total,
       SUM(CASE WHEN main_net_amt IS NOT NULL THEN 1 ELSE 0 END) AS filled
FROM moneyflow_daily WHERE stock_code = '300308';
```

### Kline data: `turnover` typically 100% NULL

The `turnover` column in `daily_kline` is frequently **100% NULL for every stock**. Any factor or calculation relying on this column produces all-NaN output.

### Kline data: `amplitude` / `amount` / `pct_change` / `change` partially NULL

The dual date format in `daily_kline` causes a data split:
- `YYYY-MM-DD` (len=10) rows: `amount`, `amplitude`, `pct_change`, `change` are **populated**
- `YYYYMMDD` (len=8) rows: these same columns are **always NULL** (only OHLCV is populated)

The len=8 rows typically cover ~127 out of 362 trading days (mid-Dec 2025 to late-Jun 2026) for affected stocks. This creates a data gap in the middle of the time series.

```sql
-- Check which stocks are affected
SELECT length(date) AS fmt, COUNT(*) AS cnt,
       SUM(CASE WHEN pct_change IS NULL THEN 1 ELSE 0 END) AS pct_null,
       MIN(date), MAX(date)
FROM daily_kline WHERE stock_code = '300308'
GROUP BY length(date);
```

### Column-quality audit template

```python
import sqlite3
conn = sqlite3.connect('stock_data.db')
for s in ['300308','002938','601138']:
    info = conn.execute(f"""
        SELECT COUNT(*) as total,
               SUM(CASE WHEN amount IS NULL OR amount=0 THEN 1 ELSE 0 END) as amount_null,
               SUM(CASE WHEN amplitude IS NULL OR amplitude=0 THEN 1 ELSE 0 END) as amp_null,
               SUM(CASE WHEN turnover IS NULL OR turnover=0 THEN 1 ELSE 0 END) as turnover_null,
               SUM(CASE WHEN pct_change IS NULL THEN 1 ELSE 0 END) as pct_null
        FROM daily_kline WHERE stock_code='{s}'
    """).fetchone()
    print(f'{s}: total={info[0]}, amount_null={info[1]}, '
          f'amp_null={info[2]}, turnover_null={info[3]}, pct_null={info[4]}')
conn.close()
```

### Date format normalization (before merging tables)

When doing pandas merges between `daily_kline` and another table, verify both sides use the same date format. If they differ, normalize before merging:

```python
# Check raw date formats first
kline_raw = conn.execute(
    "SELECT date, length(date), pct_change FROM daily_kline WHERE stock_code=? LIMIT 5",
    (code,)
).fetchall()

# Option A: normalize both sides to YYYYMMDD
df['date_key'] = df['date'].str.replace('-', '')
other['date_key'] = other['date'].str.replace('-', '')

# Option B: normalize to YYYY-MM-DD
df['date_key'] = df['date'].str.replace(
    r'(\d{4})(\d{2})(\d{2})', r'\1-\2-\3', regex=True
)
```

## References in This Skill

| File | Covers |
|------|--------|
| `references/pipeline-behavior-history.md` | Historical behavior of the pipeline across past runs |
| `references/fuyao-special-data-ingestion.md` | Fuyao special-data tables (7 tables: limit_up/down/break pools, ladder, anomaly, dragon_tiger, hot_stock) + 4-layer recipe for adding a new endpoint |
| `references/tushare-kline-pipeline-code-review.md` | **Code-level review checklist** for `qfq_tushare_daily.py`: incremental logic gap detection, batch retry patterns, date format consistency, API rate limiting, stock code filtering, logging pitfalls |

## P1 Data Facility — 7 New Analytical Tables

Starting 2026-07-09, the system includes 7 new tables for a three-layer (L1→L2→L3) analytical pipeline. These supplement the raw-data tables.

### Schema and Purpose

| Table | Layer | PK | Data Version | Purpose |
|-------|-------|----|-------------|---------|
| `market_temperature` | L1 — 大盘温度 | `trade_date` | v1 | 0~100 composite score: trend(35) + capital(35) + sentiment(30) |
| `sector_rotation` | L2 — 板块轮动 | `(trade_date, sector_code)` | v1 | 热度评分、资金流、版块涨幅、龙头股、持续性判断 |
| `leader_stocks` | L2 — 龙头股 | `(trade_date, stock_code)` | v1 | 龙头评分、连板信息、主力资金、估值过滤 |
| `valuation_daily_signal` | L3 — 日度估值信号 | `(stock_code, trade_date)` | v1 | BUY/HOLD/REDUCE/SELL信号 + 合理估值价格 |
| `decision_log` | 决策日志 | `id (AUTOINCREMENT)` | — | 三层汇总决策 + 置信度 + 执行记录 |
| `drawdown_log` | 回撤告警 | `id (AUTOINCREMENT)` | — | 回撤/温降/板块失效/止损 分级告警 |
| `valuation_sector_config` | 估值配置 | `industry_name` | — | 25行行业→估值模型映射 (buy/sell阈值) |

### ⚠️ CRITICAL: 6 of 7 Are Empty

After table creation (verified 2026-07-09):

| Table | Row Count | Status |
|-------|-----------|--------|
| `market_temperature` | **0** | 🔴 Empty |
| `sector_rotation` | **0** | 🔴 Empty |
| `leader_stocks` | **0** | 🔴 Empty |
| `decision_log` | **0** | 🔴 Empty |
| `valuation_daily_signal` | **0** | 🔴 Empty |
| `drawdown_log` | **0** | 🔴 Empty |
| `valuation_sector_config` | **25** | ✅ Populated |

**Pattern: "Empty schema"** — perfectly designed DDL with zero data. This means the L1→L2→L3 calculation pipeline is not wired up yet. The data sources (THS sector moneyflow, individual stock data) exist, but the aggregation/computation layer that populates these tables has not been built or deployed.

### Freshness Query

```python
c.execute('SELECT COUNT(*) FROM market_temperature')
c.execute('SELECT MIN(trade_date), MAX(trade_date) FROM sector_rotation')
c.execute('SELECT MIN(trade_date), MAX(trade_date) FROM leader_stocks')
c.execute('SELECT MIN(trade_date), MAX(trade_date) FROM valuation_daily_signal')
c.execute('SELECT COUNT(*) FROM valuation_sector_config')
```

### Valuation Sector Coverage Audit

The `valuation_sector_config` has 25 THS industry mappings. To audit coverage against a watchlist, you need to resolve each stock's THS industry. This requires joining through `ths_member` + either `sector_moneyflow_ths` or `industry_moneyflow_ths`:

```sql
-- Find which THS industries a stock belongs to
SELECT m.ts_code, m.con_code, m.con_name
FROM ths_member m
WHERE m.con_code = '600519.SH'
  AND m.ts_code LIKE '881%';   -- industry codes only
```

**Coverage gap**: ~65 of 90 THS industries are NOT in `valuation_sector_config`. Missing industries include: 电池(881281.TI), 风电设备(881280.TI), 元件(881270.TI), IT服务(881271.TI), 军工电子(881276.TI), 汽车零部件(881126.TI), etc. Stocks in these industries will get no `valuation_daily_signal`.

---

## THS Sector Moneyflow Tables

Two THS-based sector moneyflow tables supplement the DC `moneyflow_daily` table:

| Table | Content | Rows | Date Range | Source API |
|-------|---------|------|------------|------------|
| `sector_moneyflow_ths` | THS概念板块资金流 | 30,861 | 2026-03-10 ~ 2026-07-06 | `pro.moneyflow_cnt_ths()` |
| `industry_moneyflow_ths` | THS行业板块资金流 | 7,200 | 2026-03-10 ~ 2026-07-06 | `pro.moneyflow_ind_ths()` |
| `ths_member` | THS板块→个股映射 | 71,498 | All time | 静态快照 |

### Cron: 板块资金流向-每日增量

| Property | Value |
|----------|-------|
| Job ID | `9139d87aa0e2` |
| Shell wrapper | `~/.hermes/scripts/daily_sector_moneyflow.sh` |
| Python script | `~/my_quant_system/scripts/daily_sector_moneyflow.py` |
| Cron expression | `45 18 * * 1-5` |
| Mode | `no_agent: true` |
| Delivery | `local` |

⚠️ **Historic timing risk (now fixed):** An earlier configuration ran this at `0 16` (too early for THS data). The current schedule at **18:45** gives 45 min after the Tushare kline pipeline (18:00) and aligns with the THS moneyflow readiness window (~17:00–19:00). Reasonable but still early in the readiness window — if data is missing, the script exits silently and re-runs the next day.

### ⚠️ today_is_trade_day() Python type-comparison bug (permanent one-day lag)

`today_is_trade_day()` in `daily_sector_moneyflow.py` (and its DC twin `daily_sector_moneyflow_dc.py`) compares `row[0] == '1'` against `trade_cal.is_open`, which stores **INTEGER 1**. `int == str` is always False, so the helper silently returns False on every confirmed trade day → `get_target_date()` always picks the **previous** trade day → sector moneyflow tables land **permanently one trade day late** while cron reports `ok` and logs show a clean run.

Diagnostic signature in the cron output md: `自动检测目标日期=<前一交易日> (today=<今天>)` printed on a confirmed trade day (verify with `SELECT cal_date, is_open FROM trade_cal WHERE exchange='SSE' AND cal_date=<today>`).

Cross-source tell: when two INDEPENDENT providers (THS + DC sector moneyflow) show the SAME one-day lag, the fault is in shared calendar/target-date logic, NOT the providers. Probe the upstream directly (`pro.moneyflow_ind_ths(trade_date=...)` / `moneyflow_cnt_ths(...)` returning ~90/~387 rows for a recent trade day proves the API is healthy) before blaming the data source.

Fix: compare like-for-like (`int(row[0]) == 1`) in both scripts, then backfill the missing day with `--date <YYYYMMDD>` per script. Note SQLite numeric-coerces `is_open='1'` inside SQL, so `get_prev_trade_day()` keeps working while the Python-side check is broken — the two lookups can disagree, which is exactly how a silently-wrong helper hides next to a working one.

### `get_prev_trade_day` — Local trade_cal Pattern

The script no longer calls the Tushare API to find the previous trading day. It uses a **local-first fallback**:

```python
def get_prev_trade_day(pro=None):
    """从本地 trade_cal 表获取最近交易日，回退到昨天跳过周末。"""
    try:
        conn = sqlite3.connect(DB)
        cur = conn.execute(
            "SELECT cal_date FROM trade_cal WHERE cal_date < ? AND is_open = '1' ORDER BY cal_date DESC LIMIT 1",
            (TODAY,)
        )
        row = cur.fetchone()
        conn.close()
        if row:
            return row[0]
    except Exception:
        pass
    # 回退：昨天，跳过周六日
    d = datetime.now() - timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d.strftime('%Y%m%d')
```

**Why local is safe here** (unlike the kline/moneyflow incremental pipelines — see `references/trade-cal-staleness-pitfall.md`): This function only finds **a single date** (the most recent completed trading day). Stale local data at worst causes a redundant `INSERT OR REPLACE` of already-existing data, which is idempotent and harmless. It does **NOT** drive range-based gap detection where a stale `trade_cal` would cause the pipeline to silently skip new trading days.

### JOIN Key Format

**ths_member.ts_code ↔ sector_moneyflow_ths.sector_code:**
```
ths_member.ts_code = "885311.TI" (concept) / "881101.TI" (industry)
sector_moneyflow_ths.sector_code = "885311.TI" ✓ (same format)
industry_moneyflow_ths.industry_code = "881101.TI" ✓ (same format)
```
**Verified**: Out of 289 concept codes + 90 industry codes in ths_member, only **1 concept code** (885940.TI — "四川九洲") is missing from sector_moneyflow_ths. All 90 industry codes match perfectly.

### Schema Audit: PRIMARY KEY and INSERT Pattern

Both sector moneyflow tables define `PRIMARY KEY (trade_date, sector_code)`. The incremental script uses `df.to_sql(table, conn, if_exists='append', index=False)` — which **will crash with a UNIQUE constraint violation** if the backfill already covers that date+code combination. Use `INSERT OR REPLACE` via a cursor instead of pandas `to_sql(append)`.

---

## Comprehensive Data Pipeline Audit Checklist

When auditing the full quant data infrastructure, follow this sequence:

### Phase 1: Schema Discovery
```sql
-- Get all tables and their CREATE statements
SELECT name, sql FROM sqlite_master WHERE type='table' ORDER BY name;
```

### Phase 2: Row Count Verification
```sql
-- Identify tables that have structure but zero data
SELECT name FROM sqlite_master WHERE type='table' 
  AND NOT name LIKE 'sqlite_%'
  AND (SELECT COUNT(*) FROM "||name||") = 0;
```

### Phase 3: JOIN Key Compatibility
```sql
-- Verify format compatibility between related tables
SELECT DISTINCT substr(sector_code, 1, 3) FROM sector_moneyflow_ths;
SELECT DISTINCT substr(ts_code, 1, 3) FROM ths_member;
-- Both should share the same prefix patterns (881, 885, 886)
```

### Phase 4: Cron Configuration Audit
1. Read `~/.hermes/cron/jobs.json`
2. For each data-pipeline job, verify:
   - Schedule time vs data source readiness time
   - Script exists at the specified path
   - `last_status` is `ok` (not `error`)
   - `completed` count is increasing over time
3. Cross-reference against `cron_push_log` for failed runs

### Phase 5: Script-Level Bug Detection
Common patterns to look for in Python ETL scripts:
- `df.to_sql(..., if_exists='append')` on tables with PRIMARY KEY — will crash on duplicates
- `timedelta(days=1)` for date calculation — use `trade_cal` or API to find the previous **trading** day
- Hardcoded `yesterday` logic — breaks around weekends and holidays
- **Python reads INTEGER SQLite columns then compares against string literals** (`row[0] == '1'`) — `int == str` is silently always False, no exception. In-SQL comparisons (`WHERE is_open='1'`) DO match via SQLite coercion, so a script can ship a permanently-broken Python helper next to working SQL lookups. Audit with `SELECT typeof(col)` and compare like-for-like (`int(row[0]) == 1`)
- No `INSERT OR REPLACE` / `UPSERT` pattern for incremental data

### Phase 6: Data Coverage Analysis
- Backfill date range vs cron expected range
- For multi-source systems: which data sources are covered (THS? DC? TDX?)
- Any orphan tables (created but never populated)

## References in This Skill

| File | Covers |
|------|--------|
| `references/pipeline-behavior-history.md` | Historical behavior of the pipeline across past runs |
| `references/fuyao-special-data-ingestion.md` | Fuyao special-data tables (7 tables: limit_up/down/break pools, ladder, anomaly, dragon_tiger, hot_stock) + 4-layer recipe for adding a new endpoint |
| `references/tushare-kline-pipeline-code-review.md` | Code-level review checklist for qfq_tushare_daily.py |
| `references/backfill-procedures.md` | **Manual backfill after mass pipeline failure**: full per-table command matrix (kline/moneyflow/index/sector/margin/engines), date formats, T+1 margin caveat, engine re-run requirement, post-migration leftover cleanup, 2026-08-01 case study |
| `references/p1-facility-audit.md` | Complete P1 data facility audit report |
| `references/market-moneyflow-cron-gap.md` | **⚠️ CRITICAL**: market_moneyflow / hsgt_moneyflow have NO cron refresh path. Stale since 2026-07-03. Must create cron before P2 goes live. |
| `references/wiki-content-queries.md` | SQL patterns for generating wiki content (每日盘面, 资金流追踪, 日报归档) from stock_data.db — Top-N moneyflow, index cumulative returns, limit-up detail, anomaly stats, hot-stock daily, k-line per-date averages, **sector moneyflow, self-join for names, `main_net_amt` NULL fallback, extreme-day crash reporting patterns** |
| `references/wiki-auto-update-pipeline.md` | Daily wiki cron implementation: page layout, execution steps, and pitfalls — **append-only updates clobber frontmatter (verify `head -5` after edit), bump `updated:` dates in a second pass, YYYYMMDD vs YYYY-MM-DD inside one DB, diagnose mass pipeline failure from cron stderr before touching the DB, stale cron-prompt job dirs (use 3cb6fbcc8dcc + DB), wiki cron 03:00 runs before today's 07:05 report exists, `patch` corrupting `||` table-row prefixes, query market_temperature directly (L1 advances independently)** |

## Related Skills

- `a-share-valuation-analysis` — the daily_stock_analysis pipeline (separate project, different DB)
- `a-share-research` — research report collection via Tushare MCP
- `a-share-quant-backtest` — backtesting engine and strategy development
- `hermes-cron-pipelines` — building/debugging Hermes cron jobs with fallback patterns
- `a-share-quant-system-evaluation` — evaluates full quant system architecture (broader than single-pipeline code review)
