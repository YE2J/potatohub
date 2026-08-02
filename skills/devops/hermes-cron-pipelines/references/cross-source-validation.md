# Cross-Source Data Validation for Pipeline Quality Gates

When a data pipeline fetches from an API (Tushare, etc.) and you also have CSV files from the same data source, use cross-source validation as a **quality gate** to confirm the import is correct.

## When to Use

- You imported new data from an API and want to verify it matches a known-good reference (CSV, previous export, second API endpoint)
- You're migrating between data sources and need to validate the new source produces identical results
- A cron job produced unexpected row counts and you need to distinguish "API returned bad data" from "script bug"

## Validation Pattern

```python
# 1. Load both sources into dicts keyed by a unique identifier
csv_map = {}   # {sector_code: {fields...}}
db_map = {}    # {sector_code: {fields...}}

# 2. Check set equality
csv_codes = set(csv_map.keys())
db_codes = set(db_map.keys())

only_csv = csv_codes - db_codes      # rows missing from DB
only_db  = db_codes - csv_codes      # extra rows in DB
common   = csv_codes & db_codes      # rows present in both

# 3. Numerical comparison with tolerance (avoid float noise)
for code in common:
    if abs(csv_val['field'] - db_val['field']) > TOLERANCE:
        mismatch += 1

# 4. Rank-order comparison (top-N by a metric)
# If both sources agree on the top 5, signal quality is good
```

## Concrete Thresholds (from sector-moneyflow validation)

| Check | Threshold | Sector result |
|-------|-----------|---------------|
| Row count match | `csv_count == db_count` | 382 == 382 ✓ |
| Code set overlap | `csv_codes == db_codes` | 382/382 ✓ |
| Pct change diff | `abs(diff) <= 0.02%` | 0/382 mismatches |
| Net amount diff | `abs(diff) <= 0.5 亿` | 0/382 mismatches |
| Lead stock name | exact match | 0/382 mismatches |

## When Validation Fails

| Finding | Likely cause | Action |
|---------|-------------|--------|
| Row count differs by 1-2 | API data source slightly different composition from CSV | Check if both use the same sector classification version |
| Numerical values differ systematically | Different rounding/averaging method between sources | Compare raw data format, not rounded display values |
| Set of codes differs >10% | Completely different classification system | Don't compare; treat as independent datasets |
| Values match but rank order differs | Tiny float differences amplified by sorting | Use `isclose` with relative tolerance, not absolute |

## Validation Script Structure

The reference implementation (`/tmp/compare_sector.py`) demonstrates the full pattern:
1. Load CSV into dict (first pass)
2. Query DB into dict (second pass)
3. Compare sets, print summary
4. Deep compare numeric fields with tolerance
5. Display TOP/BOTTOM N side-by-side for visual confidence

This pattern is source-agnostic — swap the CSV reader and DB query for any two comparable datasets.
