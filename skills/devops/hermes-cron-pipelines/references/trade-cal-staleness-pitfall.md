# Trade Calendar Staleness Pitfall

## The Bug

Any cron pipeline that calls `get_latest_trade_date()` with a **local cache first, API fallback** strategy can silently skip days of new data.

### Root Cause

```python
# BROKEN: local cache first with stale-tolerant fallback
def get_latest_trade_date(pro=None):
    # Step 1: query local trade_cal table → STALE but returns data
    row = db.execute("SELECT cal_date FROM trade_cal WHERE ...")
    if row:
        return row[0]  # ← Returns 07-06 even when today is 07-09
    
    # Step 2: fallback to API (NEVER REACHED because step 1 always succeeds)
    if pro:
        df = pro.trade_cal(...)
        ...
```

The `trade_cal` sync cron runs **weekly on Monday** (`0 10 * * 1`). After Tuesday, the local table is **missing 1-4 recent trading days**, but the query still succeeds (returns the last cached date). The API fallback is never reached. The calling code then runs `has_data_for_date(stale_date)` → finds data → **skips, thinking nothing new to fetch**.

### Fix

Always query the API directly:

```python
# FIXED: API direct, no local cache
def get_latest_trade_date(pro):
    today = datetime.now().strftime("%Y%m%d")
    df = pro.trade_cal(exchange="SSE", start_date="20260101", end_date=today,
                       fields="cal_date,is_open")
    if df is not None and not df.empty:
        df = df.sort_values("cal_date", ascending=False)
        for _, row in df.iterrows():
            if row["is_open"] == 1:
                log(f"API 交易日历: 最新交易日 = {row['cal_date']}")
                return row["cal_date"]
    return None
```

Cost: one API call, ~0.5s — negligible for a daily pipeline.

### Diagnosis

If a cron job repeatedly reports "XXX数据已存在，跳过" with a stale date:

```bash
# 1. Check the stale cache
sqlite3 ~/my_quant_system/stock_data.db \
  "SELECT MAX(cal_date) FROM trade_cal WHERE exchange='SSE' AND is_open=1"

# 2. Compare against actual latest trading day via API
# (run a quick Python check)
python3 -c "
import tushare as ts
ts.set_token('your_token')
pro = ts.pro_api()
today = '20260709'
df = pro.trade_cal(exchange='SSE', start_date='20260101', end_date=today)
df = df[df['is_open']==1].sort_values('cal_date', ascending=False)
print('API latest:', df.iloc[0]['cal_date'])
"

# 3. Check cron output for the skip message
cat ~/.hermes/cron/output/<job_id>/latest.md | grep "跳过"
```

### Affected Pipelines (fixed 2026-07-09)

| Pipeline | Script | Fixed | 
|----------|--------|-------|
| 前复权日线 | `qfq_tushare_daily.py` | ✅ |
| 资金流向(DC) | `daily_moneyflow_tushare_dc.py` | ✅ |
