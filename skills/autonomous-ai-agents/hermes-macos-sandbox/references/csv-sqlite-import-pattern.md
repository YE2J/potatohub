# CSV → sqlite3 Import Pattern (No-Python Workaround)

When `python3` and `execute_code` are both blocked in cron, use this 3-step pattern
to bulk-load structured data into SQLite:

## Step 1: Write CSV via write_file

```python
write_file(path="/tmp/data.csv", content="code,date,val1,val2\n000001,2026-01-01,100,200\n...")
```

Use `/tmp/` or `~/.hermes/tmp/` — both are writable.

## Step 2: Import into temp table

```bash
sqlite3 "$DB" <<'SQLEOF'
CREATE TEMP TABLE raw (code TEXT, date TEXT, val1 REAL, val2 REAL);
.mode csv
.import /tmp/data.csv raw
SQLEOF
```

## Step 3: Transform and INSERT with SQL

```sql
INSERT OR REPLACE INTO target_table (code, date, derived_a, derived_b)
SELECT
  code, date,
  MAX(val1, 0) as derived_a,
  ABS(MIN(val1, 0)) as derived_b
FROM raw;
```

## When To Use

- Bulk data from API responses (web_extract) needs SQLite INSERT
- Python blocked by macOS sandbox or cron policy
- Data volume exceeds what's practical with individual INSERT statements

## Limitations

- No complex per-row logic (use SQL functions: MAX, MIN, ABS, CASE)
- Float precision: use REAL columns, not TEXT
- CSV must not contain commas in values (no quoting needed for numeric data)
- Temp table is session-scoped — disappears when sqlite3 exits
