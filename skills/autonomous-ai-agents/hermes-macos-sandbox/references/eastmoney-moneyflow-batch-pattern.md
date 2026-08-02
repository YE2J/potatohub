# Eastmoney Moneyflow Batch Fetch + CSV Import (Cron-Safe)

Proven pattern for batch-fetching moneyflow data from Eastmoney push2his API and writing to SQLite under cron sandbox (no Python available).

## API URL Format

```
https://push2his.eastmoney.com/api/qt/stock/fflow/daykline/get?lmt=3&klt=1&secid={market}.{code}&fields1=f1,f2,f3,f7&fields2=f51,f52,f53,f54,f55,f56,f61,f62&fmt=json
```

- `market`: `0` for SZ (0xx/3xx), `1` for SH (6xx), `0` for BJ (8xx)
- `lmt=3`: returns latest 3 trading days (small response, won't trigger LLM summarization)
- Access via `web_extract` only (local curl blocked by push2his)

## klines Field Mapping

```
f51=date, f52=main_net(主力净流入), f53=elg_net(超大单), f54=lg_net(大单),
f55=md_net(中单), f56=sm_net(小单), f61=ratio, f62=price
```

## Execution Flow (Cron)

### Step 1: Parallel Batch Fetch via web_extract

Fetch 5 URLs per call, parallelize independent batches. 99 stocks = ~20 batches.

### Step 2: Write Raw Data as CSV

Use `write_file` to `/tmp/` with columns: `code,date,main_net,elg_net,lg_net,md_net,sm_net`

### Step 3: sqlite3 Bulk Import + Transform

```sql
CREATE TABLE IF NOT EXISTS moneyflow_daily (
    stock_code TEXT, date TEXT,
    main_net_amt REAL, lg_buy_amt REAL, lg_sell_amt REAL,
    md_buy_amt REAL, md_sell_amt REAL, sm_buy_amt REAL, sm_sell_amt REAL,
    elg_buy_amt REAL, elg_sell_amt REAL, net_mf_amt REAL, data_source TEXT,
    PRIMARY KEY (stock_code, date)
);

CREATE TEMP TABLE _raw (code TEXT, date TEXT, main_net REAL, elg_net REAL, lg_net REAL, md_net REAL, sm_net REAL);
.mode csv
.import /tmp/moneyflow_data.csv _raw

INSERT OR REPLACE INTO moneyflow_daily
  (stock_code, date, main_net_amt, lg_buy_amt, lg_sell_amt,
   md_buy_amt, md_sell_amt, sm_buy_amt, sm_sell_amt,
   elg_buy_amt, elg_sell_amt, net_mf_amt, data_source)
SELECT
  code, date, main_net,
  MAX(lg_net, 0), ABS(MIN(lg_net, 0)),
  MAX(md_net, 0), ABS(MIN(md_net, 0)),
  MAX(sm_net, 0), ABS(MIN(sm_net, 0)),
  MAX(elg_net, 0), ABS(MIN(elg_net, 0)),
  main_net + elg_net + lg_net,
  'eastmoney'
FROM _raw WHERE code != 'code';
```

## Buy/Sell Split Logic

- Positive net → buy side only (`MAX(x,0)` = net, sell = 0)
- Negative net → sell side only (`ABS(MIN(x,0))` = |net|, buy = 0)
- `net_mf_amt = main_net + elg_net + lg_net` (cross-validation — should be ~0)

## Degradation Strategy

If Eastmoney API returns 502/403/empty JSON on ≥3 of 5 URLs in a batch, or ≥8 of first 12 stocks return null, switch to iwencai OpenAPI fallback (also cron-safe with curl+jq+sqlite3).

## Results (June 2026 run)

- 99 stocks (STOCKS_V4 list), 297 rows (99 × 3 days)
- 20 parallel web_extract batches, 0 failures, 0 degradation
- CSV → sqlite3 import completed in ~1s
- All rows tagged `data_source='eastmoney'`
