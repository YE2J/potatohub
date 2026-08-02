---
name: data-wiki-maintenance
description: "Maintain a wiki fed by database queries — verify data sources independently, detect table migrations, and correct propagated errors."
version: 1.1.0
author: Hermes Agent
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [wiki, database, data-pipeline, cron, verification]
    category: research
    related_skills: [llm-wiki, a-share-data-pipeline-check]
---

# Data Wiki Maintenance

Maintains a [[llm-wiki]]-style knowledge base where wiki pages track the state
of live database tables (market data, pipeline health, system status). Unlike a
purely document-based wiki, a data-fed wiki has **verification hazards**: if
the underlying data source moves, gets renamed, or the wiki tracks the wrong
table, every subsequent update compounds the error.

## When This Activates

- You are running a daily/weekly cron job that updates wiki pages from SQLite
  database tables
- You need to record the "latest date" and "health status" of multiple data
  sources (K线, 资金流, 估值, etc.)
- The data sources are SQLite tables that could be renamed, migrated, or go stale

## Key Pitfall: Compound Stale Assumptions

**The single most dangerous error in data wiki maintenance is compounding a stale
assumption across multiple runs.** This happens when:

1. Run N queries table X, finds no data, records "Table X: stagnant 1 day"
2. Run N+1 reads the log from N, reads "stagnant 1 day", increments to 2
   WITHOUT re-querying table X
3. Repeat for N+2, N+3... and days later the log says "stagnant 24 days"
   while the data was actually in table Y the whole time

## Required: Independent Source Verification Every Run

Every automated update cycle MUST independently verify each data source:

```
For each tracked data source:
  ① QUERY the actual database table/API endpoint — don't trust last session's state
  ② Check: does the table exist? Has data? Has a recent max(trade_date)?
  ③ If empty: check for ALTERNATIVE tables with similar names
     (e.g., valuation_daily_signal empty → check valuation_results)
  ④ Only THEN update the wiki page
```

### Table Verification Heuristic

```python
import sqlite3

def verify_table(db_path, expected_table, fallback_tables=None, date_column='trade_date'):
    """
    Verify a tracked database table has data. If empty, check fallbacks.
    Returns (table_name, latest_date, row_count, was_fallback) or raises.
    """
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    # Primary table check
    c.execute(f"SELECT MAX({date_column}), COUNT(*) FROM [{expected_table}]")
    max_date, count = c.fetchone()
    
    if max_date is not None and count > 0:
        return (expected_table, max_date, count, False)
    
    # Fallback scan
    if fallback_tables:
        for tbl in fallback_tables:
            try:
                c.execute(f"SELECT MAX({date_column}), COUNT(*) FROM [{tbl}]")
                d, cnt = c.fetchone()
                if d is not None and cnt > 0:
                    return (tbl, d, cnt, True)
            except sqlite3.OperationalError:
                continue
    
    conn.close()
    raise ValueError(f"No data found in {expected_table} or any fallback: {fallback_tables}")
```

## Pipeline vs Data Lag Diagnosis

A critical distinction that a data-freshness check alone **cannot** make: when a
table's latest date hasn't advanced, the root cause could be either:

| State | Meaning | How to Detect |
|-------|---------|---------------|
| **Pipeline missed** | The data-processing cron job never ran. Source data from the latest trading day was never ingested. | Check the pipeline execution log (`cron_push_log`) for the expected job run times. If no runs exist for the trading day, the pipeline missed. |
| **Pipeline ran, data unchanged** | The cron job ran but found no new source data (weekend, holiday, or source API returned nothing new). | Pipeline log shows a run entry; DB date just didn't advance. |
| **Pipeline ran, data advanced** | Normal operation. | DB date advanced since last check. |

**The `cron_push_log` table** (in `stock_data.db`) records every cron job
execution. Query it to determine which state you're in:

```sql
-- Check whether specific pipeline jobs ran on a given date
SELECT job_name, actual_time, finished_time, status, error_message
FROM cron_push_log
WHERE actual_time LIKE '2026-07-28%'  -- or target date
ORDER BY log_id DESC;
```

```sql
-- Last N pipeline executions in reverse chronological order
SELECT job_name, actual_time, finished_time, status
FROM cron_push_log
WHERE actual_time IS NOT NULL AND job_name IN (
    '前复权日线-Tushare增量', '资金流向-Tushare-DC增量',
    '指数日线-Tushare增量', '每日因子更新', '因子回填-持续'
)
ORDER BY log_id DESC LIMIT 15;
```

### Reporting the Three States

When generating a wiki update, include the **diagnosis** alongside the data dates:

- **Data advanced** → report the new date and any notable values
- **Pipeline missed** (no cron run found) → flag 🚨 distinct from ordinary stagnation.
  The data simply hasn't arrived yet — different from "data is stale"
- **Data unchanged** (cron ran but no new data) → record the stagnation count

This prevents the agent from conflating "pipeline broken" with "no new data available"
— two conditions that call for different responses.

### Daily Wiki Update Checklist

When running a cron-driven daily wiki update:

1. Query `cron_push_log` for any pipeline jobs that should have run since last check
2. Query all tracked data tables for their latest dates
3. Cross-reference: for any table that hasn't advanced, was there a pipeline run
   that should have produced data? If no → "pipeline missed". If yes → "stagnant".
4. Record the diagnosis in the wiki update, not just the raw dates
5. If a pipeline missed multiple days in a row, escalate — note the pattern

## Schema Detection

When a table seems empty, check whether it was migrated:

```python
# List all tables related to a domain
c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%valua%'")
```

Then inspect the schema of found tables:

```python
c.execute(f"PRAGMA table_info('{found_table}')")
# Look for date columns, data columns
```

## Correction Protocol

When you discover the wiki itself has been propagating an error:

1. **Log the correction first** — in log.md, with a `CORRECTION` label
2. **Update every affected page** — not just the main page, but any page that
   quoted or summarized the wrong claim
3. **Add visible correction markers** — timestamped inline sections showing
   "old claim → correction" side by side
4. **Fix root cause** — update the query/table tracking config
5. **Document the misdirection** — save a memory or update this skill so
   future runs don't repeat the same class of mistake

## Other Pitfalls

- **Don't trust fallbacks blindly** — when you find data in a fallback table,
  verify it actually contains the same schema/columns you expect. A partial
  migration may have left some columns empty.
- **Date format drift** — some tables use `YYYYMMDD` (integer), others
  `YYYY-MM-DD` (text). Always check the actual format from the schema, don't
  assume it matches what the wiki previously recorded.
- **Table may exist but be empty** — `valuation_daily_signal` had 0 rows.
  A table existing with 0 rows is a valid state (old model retired, new model
  writes elsewhere). Don't report "stagnant" until you've checked all candidates.
- **Log forward, correct backward** — always append to log.md first, then fix
  historical pages. This ensures the correction itself is timestamped and
  traceable even if the session is interrupted partway through.

## Reference Files

- `references/a-share-table-catalog.md` — Complete catalog of `stock_data.db`
  tables tracked by the wiki, with column names, date formats, and the critical
  `valuation_results` vs `valuation_daily_signal` distinction. Consult this file
  when running an A-share wiki update to know which tables to query and what
  columns to read.
