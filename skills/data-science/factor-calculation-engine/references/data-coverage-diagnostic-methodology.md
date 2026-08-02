# Data Coverage Diagnostic Methodology

> Systematic approach to diagnosing "why is my daily_factors/IC/join producing unexpectedly few results" in a SQLite-based A-share quant system.

## When to Use

- daily_factors has fewer stocks per date than expected
- IC analysis reports <5% coverage or too few valid cross-sections
- screen_v4.py in factor-table mode returns suspiciously few (or zero) hits
- Suspicion that data from different tables isn't joining correctly

## Step-by-Step Diagnostic Protocol

### Step 1: Table-Level Summary — Establish Baseline

```sql
-- daily_kline: date range, stock count, total rows
SELECT MIN(date), MAX(date), COUNT(DISTINCT date), 
       COUNT(DISTINCT stock_code), COUNT(*) FROM daily_kline;

-- daily_factors: same stats
SELECT MIN(trade_date), MAX(trade_date), COUNT(DISTINCT trade_date), 
       COUNT(DISTINCT stock_code), COUNT(*) FROM daily_factors;

-- moneyflow_daily: same, per data_source
SELECT data_source, MIN(date), MAX(date), COUNT(DISTINCT date),
       COUNT(DISTINCT stock_code), COUNT(*) FROM moneyflow_daily 
GROUP BY data_source;
```

**What to look for**: If daily_factors has 5,000 stocks but daily_kline has 10,000+ distinct codes, something is filtering. Check for InnerCode mapping loss.

### Step 2: Date-Format and Stock-Code Inventory

`daily_kline` may have two date formats AND two stock_code encoding systems simultaneously:

```sql
-- Inventory by date format (length check)
SELECT LENGTH(date), COUNT(*) as rows, COUNT(DISTINCT date) as days,
       COUNT(DISTINCT stock_code) as stocks
FROM daily_kline GROUP BY LENGTH(date);

-- Inventory by stock_code format (6-digit vs non-standard)
SELECT 
  SUM(CASE WHEN stock_code GLOB '[0-9][0-9][0-9][0-9][0-9][0-9]' THEN 1 ELSE 0 END) as six_digit_numeric,
  SUM(CASE WHEN NOT (stock_code GLOB '[0-9][0-9][0-9][0-9][0-9][0-9]') THEN 1 ELSE 0 END) as non_standard
FROM daily_kline WHERE date = (SELECT MAX(date) FROM daily_kline);
```

**Expectations**:
- 6-digit numeric codes → SecuCode (matches daily_factors)
- Non-6-digit codes (10000, 10017, etc.) → InnerCodes → **need mapping**
- Different date lengths (`8` and `10`) → **two separate data sources merged into one table**

### Step 3: Per-Date Stock Count — Check Drift

```sql
SELECT date, COUNT(DISTINCT stock_code) as stocks 
FROM daily_kline GROUP BY date ORDER BY date;
```

A drop from 5,000+ to 2 stocks before a certain date means one data source starts earlier than another.

### Step 4: Check InnerCode→SecuCode Mapping Completeness

```sql
-- What fraction of daily_kline stock_codes map to SecuCodes?
-- Run this in Python (SQLite can't do CSV JOIN)
import csv, sqlite3
inner_to_secu = {}
with open('all_ashare_stocks.csv') as f:
    for r in csv.DictReader(f):
        inner_to_secu[r['InnerCode']] = r['SecuCode']

conn = sqlite3.connect('stock_data.db')
codes = [r[0] for r in conn.execute(
    "SELECT DISTINCT stock_code FROM daily_kline WHERE date='2024-06-03'").fetchall()]
conn.close()

mapped = sum(1 for c in codes if c in inner_to_secu)
total = len(codes)
print(f"Mapped: {mapped}/{total} ({mapped/total*100:.1f}%)")
```

### Step 5: JOIN Match Audit — Factor Table vs Kline Table

```sql
-- The critical query: how many daily_factors rows have kline close prices?
SELECT f.trade_date, 
       COUNT(*) as factor_rows,
       SUM(CASE WHEN k.close IS NOT NULL THEN 1 ELSE 0 END) as matched,
       SUM(CASE WHEN k.close IS NULL THEN 1 ELSE 0 END) as unmatched
FROM daily_factors f
LEFT JOIN daily_kline k 
  ON f.stock_code = k.stock_code 
  AND (f.trade_date = k.date OR REPLACE(f.trade_date, '-', '') = k.date)
WHERE f.trade_date IN ('2024-06-03', '2026-06-24', '2026-06-25')
GROUP BY f.trade_date;
```

If matched < 5% of factor_rows, the JOIN is failing. The two most common causes:
1. **InnerCode↔SecuCode mismatch** (daily_kline uses InnerCodes, daily_factors uses SecuCodes)
2. **Date format mismatch** (one side uses YYYY-MM-DD, the other YYYYMMDD)

### Step 6: Verify the Fix Candidates

**Candidate 1 — Date format mismatch**: Check if the 8-digit format provides the matching stocks:
```sql
SELECT f.stock_code, k.date, k.close, f.gs_g_point
FROM daily_kline k
JOIN daily_factors f ON k.stock_code = f.stock_code 
  AND REPLACE(f.trade_date, '-', '') = k.date
WHERE k.date IN ('20260624', '20260625') AND k.close IS NOT NULL
LIMIT 10;
```

**Candidate 2 — InnerCode in 10-digit format**: Check the 10-digit format stock codes:
```sql
SELECT DISTINCT stock_code FROM daily_kline 
WHERE date = '2026-06-24' AND LENGTH(date) = 10
  AND NOT (stock_code GLOB '[0-9][0-9][0-9][0-9][0-9][0-9]')
LIMIT 20;
```

If Candidate 1 returns ~142 stocks (watchlist only) and Candidate 2 shows InnerCodes (10000, 10017, etc.), the root cause is confirmed.

### Step 7: Measure the Backfill Gap

```sql
-- How many trading days per year does daily_factors actually cover?
SELECT SUBSTR(trade_date, 1, 4) as year,
       COUNT(DISTINCT trade_date) as trading_days,
       ROUND(AVG(cnt)) as avg_stocks,
       MIN(cnt) as min_stocks, MAX(cnt) as max_stocks
FROM (SELECT trade_date, COUNT(*) as cnt FROM daily_factors GROUP BY trade_date)
GROUP BY year ORDER BY year;

-- Compare with daily_kline trading days
SELECT SUBSTR(date, 1, 4) as year, COUNT(DISTINCT date) as kline_days
FROM daily_kline GROUP BY year ORDER BY year;
```

The difference between `trading_days` and `kline_days` per year = the backfill gap.

## Putting It All Together: Diagnostic Decision Tree

```
Start: daily_factors / IC analysis producing suspicious results
│
├─ Run Step 1 (table-level stats)
│  ├─ daily_factors has 0 rows? → Factor pipeline never ran (backfill needed)
│  └─ daily_factors has expected counts → Go to Step 5
│
├─ Run Step 5 (JOIN match audit)
│  ├─ matched > 90%? → Problem is elsewhere (check factor values, thresholds)
│  └─ matched < 10%? → Root cause confirmed
│       │
│       ├─ Run Step 6 Candidate 1 → Returns ~142 stocks?
│       │   → Problem: only 8-digit date format matches. 10-digit format uses InnerCodes.
│       │   → Fix: Apply InnerCode→SecuCode mapping in _load_kline()
│       │
│       └─ Run Step 6 Candidate 2 → Shows InnerCodes?
│           → daily_kline stocks are InnerCodes, daily_factors uses SecuCodes
│           → Fix: Map InnerCode→SecuCode before the JOIN
│
├─ Run Step 7 (backfill gap)
│  ├─ Years with 0 factor trading_days but 200+ kline_days?
│  │   → Full year gap: backfill never covered these dates
│  │   → Fix: Run backfill_cron.sh for the missing year range
│  └─ Expected coverage → Problem is purely the JOIN
```

## Common Symptoms → Root Cause

| Symptom | Root Cause | Fix |
|---------|-----------|-----|
| IC reports 3-14 valid stocks per cross-section | _load_kline() lacks InnerCode mapping | Add mapping to _load_kline() |
| screen_v4 factor mode returns 0 hits but fallback mode returns 20+ | Factor pipeline computed wrong values (possibly MONEY=0 bug) | Check MONEY injection in factors.py |
| daily_factors has 5,000+ stocks but kline JOIN yields <50 | InnerCode/SecuCode mismatch | Apply bidirectional mapping |
| daily_factors only has 2024 + 3 days in 2026 | Backfill stopped mid-way | Resume backfill for 2025 + 2026-01~06 |
| kline has 10,000+ distinct codes but daily_factors only 5,000 | InnerCode mapping silently dropping un-mappable stocks | Check all_ashare_stocks.csv completeness |
| Per-date stock count drops from 5,000 to 2 before date X | Two different kline data sources merged | InnerCode format (full market) vs SecuCode format (watchlist) |
