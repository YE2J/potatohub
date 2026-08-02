# No-Agent Data Report Script — 3-Agent Review Checklist

Checklist for reviewing `no_agent=true` Python scripts that query local DB + cron output files and produce formatted report output (e.g., morning reports, daily summaries).

## Architecture & Design Review

### Data Sources
- [ ] SQL column names verified against actual `PRAGMA table_info()` — never assume names match
- [ ] Date format consistency: `YYYY-MM-DD` vs `YYYYMMDD` — treat with `REPLACE(date,'-','')` in ORDER BY
- [ ] Database connection: `try/finally` or `with` to guarantee `conn.close()`
- [ ] File paths: `os.path.expanduser()` or `get_hermes_home()` — no hardcoded `~`
- [ ] Cron output file reading: sorted by mtime, not just filename (filename sort fails if format changes)

### Output Format
- [ ] Markdown table truncation safety: if truncating by char, detect rows starting with `|` and rewind to table boundary
- [ ] Module-priority truncation: define which sections are more important and trim lower-priority ones first
- [ ] Channel char limit (WeChat iLink ≈ 4000, reserve 80 for truncation notice)
- [ ] Empty/null data: show `—` not blank or crash

### Configuration
- [ ] Threshold constants named (e.g., `THRESHOLD_OK=26`, `THRESHOLD_WARN=48`)
- [ ] `CRON_JOBS` hardcoded job_ids — add note that Hermes restart invalidates them
- [ ] Paths as module-level constants, not scattered in functions

## Data Logic & Correctness Review

### Date Handling
- [ ] Monday morning: `datetime.now() - timedelta(days=1)` returns Sunday → cron jobs don't run, Hermes report missing
- [ ] Unified trade date: all modules should agree on "what day is today's report about"
- [ ] Use `get_latest_trade_date()` from DB as the authoritative date, not calendar arithmetic

### SQL Queries
- [ ] `COUNT(DISTINCT col)` vs `COUNT(*)`: DISTINCT is more expensive; know when PK already guarantees uniqueness
- [ ] Does `SUM(main_net_amt)` have the right index? `EXPLAIN QUERY PLAN` before shipping
- [ ] `try/except sqlite3.Error` — print the error, don't `except: pass`
- [ ] Hidden column mismatches: `north_money` vs actual `north_total` → caught only by checking `PRAGMA table_info`

### Data Quality
- [ ] Cross-field consistency: if `main_net_amt ≈ net_mf_amt` for all rows, data pipeline may be broken → warn user
- [ ] Zero-division protection in ratio calculations
- [ ] None/null propagation: every `fmt_*` function must handle `None` input

## SRE & Robustness Review

### Failure Modes
- [ ] DB file doesn't exist: graceful message, not traceback
- [ ] Directory `~/.logs/` doesn't exist: `os.path.exists()` check
- [ ] Cron output directory empty: return `(None, None)`, caller shows "无运行记录"
- [ ] `os.path.getmtime()` can throw `OSError` on exotic filesystems
- [ ] Connection without WAL: read locks block writes → use `timeout=10` or WAL mode

### Cron Output Parsing
- [ ] Regex patterns brittle: if cron script changes output format, regex silently returns nothing
- [ ] Fallback when no metric matches: show "已运行" instead of blank
- [ ] Multiple for-loop passes over `content.split('\n')` → merge into single pass

### Log File Checks
- [ ] `report_data_status()` checks log file mtime against configurable threshold constants
- [ ] When a pipeline is permanently removed, also remove its pipeline check

## Common Findings From Real Reviews

### Morning report v5.3 review (2026-07-07)

| Finding | Severity | Fix |
|---------|----------|-----|
| SQL column name mismatch → silent failure | 🔴 P0 | Check `PRAGMA table_info`, fix query |
| No `try/finally` on DB connection → leak on exception | 🔴 P0 | Wrap `main()` body in `try/finally` |
| Monday calendar day ≠ trade day | 🔴 P0 | Use DB `MAX(date)` for unified date |
| `net_mf_amt ≈ main_net_amt` (data pipeline bug) | 🔴 P0 | Show quality warning to user |
| Three for-loops over same `content.split('\\n')` | 🟢 P2 | Merge into single pass |
| Dead code `if ...: pass` | 🟢 P2 | Remove |
| Magic number thresholds (26 vs 30 with no comment) | 🟡 P1 | Named constants |
| Truncation breaks table mid-way | 🟡 P1 | Rewind to table boundary |
| Cron format change → silent blank column | 🟡 P1 | Add "已运行" fallback |

### Moneyflow field mapping review (2026-07-09)

| Finding | Severity | Fix |
|---------|----------|-----|
| `buy_elg_amount` written to `elg_net_amt` (buy != net) | 🔴 P0 | Map to buy columns, set net=NULL |
| `net_amount` written to `main_net_amt` (总净额≠主力) | 🔴 P0 | `main_net_amt=None`, only `net_mf_amt` gets value |
| `net_mf_amt == main_net_amt` always (redundant) | 🔴 P0 | Eliminate redundancy, each column has distinct semantics |
| PK lacks `data_source` → cross-source overwrite | 🟡 P1 | Add `data_source` to PK or use MERGE pattern |
| retry only 1 attempt at 30s | 🟡 P1 | Exponential backoff: 30s → 90s → 270s |
| no partial-data protection (threshold + row count check) | 🟡 P1 | Log row count vs expected; warn on short data |

### Moneyflow north-bound unit mismatch (2026-07-09)

| Finding | Severity | Fix |
|---------|----------|-----|
| North-bound money: `fmt_money` treated 万元 as 元 → `+0.00亿` | 🔴 P0 | Added `unit` param: `fmt_money(val, 'wan')` divides by 1e4 instead of 1e8 |
