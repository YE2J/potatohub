# Batch Historical Data Fill via Installed Tushare Python Library

Beyond MCP, the `tushare` Python library (`import tushare as ts`) is installed in the active pyenv and can be used for batch operations that would be too heavy or slow via individual MCP calls.

## Token Setup

The Tushare token is **not** in `~/.tushare/token` or env vars — it's embedded in the MCP server URL in `~/.hermes/config.yaml`:

```yaml
tushareMcp:
  url: https://api.tushare.pro/mcp/?token=<TOKEN>
```

Extract and set in Python:

```python
import tushare as ts
TS_TOKEN = "6570d7ea1f9ab8dece97e18afb1e3e814c681b4b9bc6d3841ddd7e8e"
ts.set_token(TS_TOKEN)
pro = ts.pro_api()
```

## Batch Fill Pattern

Fill a date range of daily data for a list of stocks, skipping already-existing rows:

```python
import sqlite3, time
import tushare as ts
import pandas as pd

ts.set_token(TOKEN)
pro = ts.pro_api()
conn = sqlite3.connect('stock_data.db')
cur = conn.cursor()

stocks = {
    '300308': '300308.SZ',  # bare_code: ts_code
    '300502': '300502.SZ',
    # ...
}

for bare_code, ts_code in stocks.items():
    # 1. Check current coverage
    cnt = cur.execute(
        "SELECT COUNT(*) FROM daily_kline WHERE stock_code=?", (bare_code,)
    ).fetchone()[0]
    
    # 2. Fetch from Tushare
    df = pro.daily(ts_code=ts_code, start_date='20250101', end_date='20251214')
    if df is None or len(df) == 0:
        continue
    
    # 3. Normalize date format (YYYYMMDD → YYYY-MM-DD)
    rows = []
    for _, r in df.iterrows():
        d = r['trade_date']
        d = f"{d[:4]}-{d[4:6]}-{d[6:8]}"
        rows.append((
            bare_code, d, r['open'], r['high'], r['low'], r['close'],
            r['vol'], r['amount'], r['pct_chg'], r['change']
        ))
    
    # 4. INSERT OR IGNORE (batch)
    cur.executemany("""
        INSERT OR IGNORE INTO daily_kline 
        (stock_code, date, open, high, low, close, volume, amount, pct_change, change)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, rows)
    conn.commit()
    
    # 5. Verify
    new_cnt = cur.execute(
        "SELECT COUNT(*) FROM daily_kline WHERE stock_code=?", (bare_code,)
    ).fetchone()[0]
    
    # 6. Tushare rate limit: 500次/分钟 → 0.35s delay safe
    time.sleep(0.35)
```

## Key Points

- **Rate limit**: 500 calls/min → add `time.sleep(0.35)` between independent calls
- **No duplicate insert**: Use `INSERT OR IGNORE` — key is (stock_code, date)
- **Verify before and after**: Check row count + MIN/MAX dates for coverage
- **Date format**: `daily_kline.date` uses `YYYY-MM-DD` (dash format); Tushare returns `YYYYMMDD`
- **Column mapping**: `vol→volume`, `pct_chg→pct_change`, `amount→amount` (keep as-is, Tushare amounts are in yuan)
- **Amplitude/turnover**: These columns can be left NULL; `pct_chg` is mandatory

## When to Use vs MCP

| Method | When | Why |
|--------|------|-----|
| MCP (`mcp_tushareMcp_daily`) | 1-6 stocks, quick lookup | Zero setup, no token handling |
| Python library (`pro.daily()`) | 7+ stocks or batch backfill | Loop + rate-limit-aware + executemany |
