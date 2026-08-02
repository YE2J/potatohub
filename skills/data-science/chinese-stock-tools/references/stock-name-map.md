# Stock Code → Name Mapping (stock_name_map)

## Problem

Many A-share data tables store only `stock_code` (6-digit number or with `.SZ`/`.SH` suffix) but not the human-readable `stock_name`. Examples:
- `moneyflow_daily` — 14M+ rows, stock_code only
- `daily_kline` — 2.6M+ rows, stock_code only
- Any imported CSV data where the filename was used as code

The morning report (每日晨报) needs to display the stock name alongside the code (e.g. "新易盛(300502)" instead of just "300502").

## Solution: Composite Mapping Table

Create a `stock_name_map` table in `stock_data.db` with codes from multiple data sources:

```sql
CREATE TABLE IF NOT EXISTS stock_name_map (
    stock_code TEXT PRIMARY KEY,
    stock_name TEXT NOT NULL,
    source TEXT DEFAULT 'ths'
);
```

### Data Sources (in order of coverage)

| Source | Coverage | Method |
|--------|----------|--------|
| `ths_member` | 5,541 codes | `substr(con_code, 1, 6)`, covers concept/sector member stocks |
| Tushare stock_basic (L) | 5,528 codes | `pro.stock_basic(list_status='L')`, all listed A-shares |
| Tushare stock_basic (D) | 337 codes | `pro.stock_basic(list_status='D')`, delisted stocks |

**Final coverage**: 5,861 / 5,979 distinct codes in `moneyflow_daily` = **98%**. Remaining 118 are B-shares (200xxx/900xxx) with zero or negligible fund-flow activity — they never appear in real TOP5 output.

### Stock Code Format Handling

The mapping must handle **two formats** that coexist in the database:

| Format | Example | Tables where found |
|--------|---------|--------------------|
| 6-digit | `000001` | `moneyflow_daily` (14.3M rows, 5,979 distinct) |
| With suffix | `000001.SZ` | `ths_member.con_code`, some `moneyflow_daily` rows (26K) |

The mapping table stores **both formats** as separate entries with different `source` values:
- `source='ths'` / `source='tushare'` → 6-digit code
- `source='ths_suffix'` / `source='tushare_suffix'` → suffixed code (e.g. `000001.SZ`)
- `source='tushare_delisted'` → 6-digit code of delisted stocks
- `source='tushare_delisted_suffix'` → suffixed code of delisted stocks

This allows LEFT JOIN to match regardless of which format the source table uses.

### LEFT JOIN Pattern (Morning Report)

```python
# Before: code only
SELECT stock_code, net_mf_amt
FROM moneyflow_daily
WHERE date = ?
ORDER BY net_mf_amt DESC LIMIT 5

# After: code + name
SELECT m.stock_code, m.net_mf_amt,
       COALESCE(s.stock_name, '') as stock_name
FROM moneyflow_daily m
LEFT JOIN stock_name_map s ON m.stock_code = s.stock_code
WHERE m.date = ?
ORDER BY m.net_mf_amt DESC LIMIT 5

# Output
label = f"{name}({code})" if name else code
```

### Build Script (one-time)

```python
import tushare as ts
pro = ts.pro_api()

# From ths_member (sector membership)
conn.execute("""
    INSERT OR IGNORE INTO stock_name_map (stock_code, stock_name, source)
    SELECT DISTINCT substr(con_code, 1, 6), con_name, 'ths'
    FROM ths_member
""")

# From Tushare listed stocks
df_l = pro.stock_basic(list_status='L', fields='ts_code,symbol,name')
df_d = pro.stock_basic(list_status='D', fields='ts_code,symbol,name')
for _, row in pd.concat([df_l, df_d]).iterrows():
    conn.execute("INSERT OR IGNORE INTO stock_name_map (...) VALUES (?, ?, 'tushare')",
                 (row['symbol'], row['name']))
    conn.execute("INSERT OR IGNORE INTO stock_name_map (...) VALUES (?, ?, 'tushare_suffix')",
                 (row['ts_code'], row['name']))
```

### Notes on Delisted Stock Names

Tushare's delisted stock names include a suffix marker like `(退)` or `XX退` (e.g. `海通证券(退)`, `退鹏博(退)`). This is intentional — it alerts the user in the morning report that the stock is no longer actively traded. The TOP5 filter (ORDER BY net_mf_amt DESC) naturally excludes most delisted stocks since they have negligible fund flow activity.

### Performance

With a PRIMARY KEY on `stock_code`, the LEFT JOIN is essentially an indexed lookup:
- Full scan of 5,843 rows: **~1.37ms** with the index
- Without index: **~19.8ms** full table scan
- **Always ensure the PK index exists** before deploying the JOIN.
