# East Money Moneyflow API — Batch Ingestion Pipeline

Batch-fetch A-share stock moneyflow (主力资金流向) data from East Money's
public API and write it incrementally to a SQLite database.

## API Endpoint

```
https://push2his.eastmoney.com/api/qt/stock/fflow/daykline/get
  ?lmt=3           ← 3 = latest 3 trading days (incremental)
  &klt=1            ← daily K-line
  &secid={market}.{code}   ← 0.000001 for SZ, 1.600000 for SH
  &fields1=f1,f2,f3,f7
  &fields2=f51,f52,f53,f54,f55,f56,f61,f62
  &fmt=json
```

### secid Rule

- Code starts with `6` (SH) → `1.{code}` (e.g. `1.600008`)
- Everything else (SZ) → `0.{code}` (e.g. `0.000626`, `0.300088`, `0.688519`)

## Access Pattern

**Only `web_extract` works.** Local curl / Python requests / urllib all get
`Remote end closed connection without response`. The API is geofenced or
requires a specific TLS profile that only Hermes's web_extract backend
provides.

**lmt ≤ 3 is critical.** Values over ~50 cause web_extract to return an
LLM summary instead of raw JSON. Use lmt=3 for incremental daily updates.

## Response Format (klines)

Each kline string: `date,f52,f53,f54,f55,f56,f61,f62`

| Field | Meaning | Direction |
|-------|---------|-----------|
| f51 | 日期 | YYYY-MM-DD |
| f52 | 主力净流入 | Net (sum of f53+f54) |
| f53 | 超大单净流入 | Net; positive=inflow |
| f54 | 大单净流入 | Net; positive=inflow |
| f55 | 中单净流入 | Net; positive=inflow |
| f56 | 小单净流入 | Net; positive=inflow |
| f61 | 主力净流入占比(%) | — |
| f62 | 收盘价 | — |

## Field Mapping → SQLite

```python
main_net_amt = f52
elg_buy = max(f53, 0); elg_sell = abs(min(f53, 0))
lg_buy  = max(f54, 0); lg_sell  = abs(min(f54, 0))
md_buy  = max(f55, 0); md_sell  = abs(min(f55, 0))
sm_buy  = max(f56, 0); sm_sell  = abs(min(f56, 0))
net_mf_amt = f52 + f53 + f54  # checksum (should ≈ 0)
data_source = 'eastmoney'
```

## SQLite Table

```sql
CREATE TABLE moneyflow_daily (
    stock_code TEXT, date TEXT,
    main_net_amt REAL, lg_buy_amt REAL, lg_sell_amt REAL,
    md_buy_amt REAL, md_sell_amt REAL, sm_buy_amt REAL, sm_sell_amt REAL,
    elg_buy_amt REAL, elg_sell_amt REAL, net_mf_amt REAL, data_source TEXT,
    PRIMARY KEY (stock_code, date)
);
```

Use `INSERT OR REPLACE` for idempotency.

## Batch Processing Pattern

For large watchlists (50+ stocks), the efficient pattern is:

1. **Build URLs** — **4 stocks per `web_extract` call** (5 is the URL cap,
   but 4 is more reliable given ~10% 504 timeout rate; a batch of 5 that
   loses 1 stock to a timeout means re-fetching a mostly-successful batch).
2. **Handle timeouts** — ~10% of batches 504-timeout. Retry on 2nd attempt
   usually succeeds. Mark persistent failures (3+ attempts) and report them.
   Do NOT re-fetch entire batches — individual stock URLs are independent.
3. **Save raw outputs** after each successful fetch. For cron jobs, embed
   parsed klines directly in a generated Python script (see pattern below).
4. **Parse & write** with `INSERT OR REPLACE` for idempotency.

This avoids the pitfall of manual kline transcription (error-prone and slow).

## Cron Mode Considerations

When running as a Hermes cron job:

- **`execute_code` is blocked for cron jobs** — you cannot use `execute_code`
  to run inline Python for safety reasons. Use normal tools only.
- **`python3` is blocked in cron sandbox** (macOS TCC + xcode-select shim).
  Do NOT rely on `terminal("python3 ...")` in cron — it will fail with
  `Operation not permitted`. Use `sqlite3` CLI + `jq` + `curl` instead.
- **CSV → sqlite3 `.import` pattern**: write data as CSV via `write_file`,
  then `sqlite3 ".mode csv" + ".import"` into a temp table, compute derived
  columns with SQL functions (MAX, MIN, ABS, CASE), and `INSERT OR REPLACE`
  into the target table. No Python required. See the
  `hermes-macos-sandbox` skill's `references/csv-sqlite-import-pattern.md`.
- **`write_file` works normally** (to `~/.hermes/` or `/tmp/`) — stage
  scripts/data there, but run sqlite3 directly, not Python.
- **Total row count** = stocks × `lmt` (e.g., 99 × 3 = 297 rows per run).

## Run Example (Cron Session — No Python)

```text
# 1. web_extract 5 stocks per call, ~20 calls for 99 stocks
# 2. All 20 batches should return valid JSON (rc=0) with klines arrays
# 3. write_file: dump all klines as CSV to /tmp/mf_raw.csv
#    Format: code,date,f52,f53,f54,f55,f56
# 4. sqlite3: import CSV into temp table, compute derived fields with SQL:
#    sqlite3 "$DB" "
#      CREATE TEMP TABLE raw (...); .mode csv; .import /tmp/mf_raw.csv raw;
#      INSERT OR REPLACE INTO moneyflow_daily (...) SELECT ... FROM raw;
#    "
# 5. sqlite3: verify:
#    SELECT COUNT(*), MIN(date), MAX(date) FROM moneyflow_daily WHERE date >= '...';
#    → e.g. "297 rows (2026-06-16 ~ 2026-06-18)"
```

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| 504 from web_extract | Firecrawl upstream timeout (~10% of requests) | Retry once or twice; individual URL retry, not whole batch |
| Empty response (no error) | Stock may be suspended/stopped — `klines` array is empty or `data` is absent | Skip silently — not an error |
| Fewer than expected rows | lmt too large (>50) triggers LLM summary instead of raw JSON | Enforce `lmt=3` for daily cron, `lmt≤50` for backfill |

## Schema & Insert

```sql
CREATE TABLE moneyflow_daily (
    stock_code TEXT, date TEXT,
    main_net_amt REAL, lg_buy_amt REAL, lg_sell_amt REAL,
    md_buy_amt REAL, md_sell_amt REAL, sm_buy_amt REAL, sm_sell_amt REAL,
    elg_buy_amt REAL, elg_sell_amt REAL, net_mf_amt REAL, data_source TEXT,
    PRIMARY KEY (stock_code, date)
);
```

Use `INSERT OR REPLACE` — same stock+date always overwrites. Safe to re-run.

## Example: Full Pipeline for 99 Stocks (No Python)

```bash
# 1. Fetch in 5-URL batches (20 batches for 99 stocks) via web_extract
# 2. Accumulate all klines into CSV format
# 3. Import via sqlite3 (no python3 needed in cron)
sqlite3 ~/my_quant_system/stock_data.db <<'SQLEOF'
CREATE TEMP TABLE raw (code TEXT, date TEXT, main_net REAL, elg REAL, lg REAL, md REAL, sm REAL);
.mode csv
.import /tmp/mf_raw.csv raw
INSERT OR REPLACE INTO moneyflow_daily
  (stock_code, date, main_net_amt, elg_buy_amt, elg_sell_amt,
   lg_buy_amt, lg_sell_amt, md_buy_amt, md_sell_amt,
   sm_buy_amt, sm_sell_amt, net_mf_amt, data_source)
SELECT code, date, main_net,
  MAX(elg,0), ABS(MIN(elg,0)), MAX(lg,0), ABS(MIN(lg,0)),
  MAX(md,0), ABS(MIN(md,0)), MAX(sm,0), ABS(MIN(sm,0)),
  elg+lg+md+sm, 'eastmoney'
FROM raw;
SQLEOF

# 4. Verify
sqlite3 ~/my_quant_system/stock_data.db \
  "SELECT COUNT(*), MIN(date), MAX(date) FROM moneyflow_daily WHERE date >= '2026-06-16'"
```
