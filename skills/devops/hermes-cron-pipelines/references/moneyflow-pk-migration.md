# moneyflow_daily PK Migration: Adding data_source

## Problem

The `moneyflow_daily` table had `PRIMARY KEY (stock_code, date)` **without** `data_source`. Four data sources (ths, tushare_dc, ths_snapshot, eastmoney) coexist in the table. `INSERT OR REPLACE` on the same stock+date from different sources would silently overwrite each other's rows — including the `data_source` tag itself.

## Migration (SQLite)

SQLite does not support `ALTER TABLE ... ADD PRIMARY KEY`. Full table recreation is required:

```sql
-- 1. Create new table with compound PK
CREATE TABLE moneyflow_daily_new (
    stock_code TEXT,
    date TEXT,
    main_net_amt REAL,
    lg_buy_amt REAL,
    lg_sell_amt REAL,
    md_buy_amt REAL,
    md_sell_amt REAL,
    sm_buy_amt REAL,
    sm_sell_amt REAL,
    elg_buy_amt REAL,
    elg_sell_amt REAL,
    net_mf_amt REAL,
    data_source TEXT,
    elg_buy_vol REAL DEFAULT 0,
    elg_sell_vol REAL DEFAULT 0,
    lg_buy_vol REAL DEFAULT 0,
    lg_sell_vol REAL DEFAULT 0,
    md_buy_vol REAL DEFAULT 0,
    md_sell_vol REAL DEFAULT 0,
    sm_buy_vol REAL DEFAULT 0,
    sm_sell_vol REAL DEFAULT 0,
    net_mf_vol REAL DEFAULT 0,
    elg_net_amt REAL DEFAULT 0,
    lg_net_amt REAL DEFAULT 0,
    md_net_amt REAL DEFAULT 0,
    sm_net_amt REAL DEFAULT 0,
    raw_json TEXT DEFAULT '',
    PRIMARY KEY (stock_code, date, data_source)  -- ← key change
);

-- 2. Copy all data (INSERT ... SELECT *)
INSERT INTO moneyflow_daily_new SELECT * FROM moneyflow_daily;

-- 3. Verify row count matches
SELECT COUNT(*) FROM moneyflow_daily;
SELECT COUNT(*) FROM moneyflow_daily_new;

-- 4. Swap tables
DROP TABLE moneyflow_daily;
ALTER TABLE moneyflow_daily_new RENAME TO moneyflow_daily;

-- 5. Rebuild indexes
CREATE INDEX IF NOT EXISTS idx_mf_date ON moneyflow_daily(date);
CREATE INDEX IF NOT EXISTS idx_mf_source ON moneyflow_daily(data_source);
```

## Verification

After migration:
- `PRAGMA table_info(moneyflow_daily)` should show `pk` column as the last 3 columns (stock_code, date, data_source)
- Query: `SELECT data_source, COUNT(*) FROM moneyflow_daily GROUP BY data_source` — all original sources still present with correct row counts
- The `INSERT OR REPLACE` in individual pipeline scripts needs NO changes — the new PK automatically prevents cross-source overwrites

## Impact

- 14,272,709 rows migrated successfully in ~2 seconds on local SSD
- Zero data loss (pre-migration count == post-migration count)
- Downstream queries continue working unchanged (PK change is transparent to SELECT)
- The `net_mf_amt` and `main_net_amt` always-equal redundancy is NOT fixed by this migration — it's a separate schema issue
