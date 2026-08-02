---
name: codebase-quality-review
description: "Cross-file architecture & consistency audit — schema alignment, date format compatibility, default value risks, config drift, cron/infra integrity, and file permission checks."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [code-review, architecture, audit, consistency, data-quality, cron]
    related_skills: [requesting-code-review, systematic-debugging, plan, github-code-review]
---

# Codebase Quality & Architecture Review

Systematic cross-file audit for structural defects, data pipeline integrity issues, config drift, and operational risks. Unlike `requesting-code-review` (which checks a git diff before commit), this skill scans the **entire relevant codebase** holistically.

## When to Use

- User asks: "review code quality", "architecture review", "check consistency", "audit the system", "cross-file check"
- Before major refactoring — establish baseline defects
- After merging multiple feature branches — detect integration mismatches
- When onboarding to an unfamiliar codebase — find silent failure modes

**This skill vs `requesting-code-review`:** That skill checks YOUR working-tree diff before commit. This skill checks the HEAD state (or an arbitrary set of files) for structural issues that span multiple files, modules, or data layers.

## Workflow

### Step 1 — Scope identification

Ask or infer what to scan. Common triggers:
```
"review my changes in the quant system"
"check backtest_v4.py and screen_v4.py"
"audit the whole strategy_library/"
```

If the scope is unclear, look for:
- Recently modified files (`git log --oneline --name-only -5`)
- Files the user mentioned
- Entry points (CLI scripts, pipeline orchestration scripts, cron wrappers)
- Config/constants files

### Step 2 — Parallel file read (always batch independent reads)

Read ALL target files in a single turn. Never serialize independent reads.
Target files typically include:

| Role | Typical files |
|------|--------------|
| Entry point / CLI | `scripts/*.py`, `scripts/*.sh` |
| Core logic | `backtest*.py`, `screen*.py`, `analyze*.py` |
| Config | `config.py`, `settings.py`, `*.yaml`, `*.toml` |
| DB schema | `*ddl.sql`, `*schema.sql` |
| Pipeline | `bridge.py`, `app/main.py` |
| Cron / ops | `.hermes/profiles/*/cron/*`, `crontab`, `scripts/*.sh` |

### Step 3 — Run the Check Matrix

Use the checklist below. For each check, scan the raw file content (not summaries).

#### 🔴 Check 1: Schema ↔ Code Consistency (Table Alignment)

Verify that column names used in SQL queries match the actual DDL.

```python
# Patterns to find:
# DDL says:  trade_date TEXT
# Query says: ON ... f1.stock_code = f2.stock_code AND f2.trade_date = ...
#             ^^^^ match? Or does it use 'date' where DDL says 'trade_date'?

# KEY areas:
# 1. INSERT column list vs DDL column order
# 2. SELECT aliases vs downstream field access
# 3. UPSERT / INSERT OR REPLACE column count vs value count
```

**What to check:**
- Column names in INSERT/UPDATE match DDL exactly
- Column count in VALUES matches column list in INSERT
- JOIN columns exist in both tables with compatible types
- Views reference columns that still exist (no stale columns from a dropped migration)
- **🔴 PK completeness**: Does the PRIMARY KEY include ALL dimensions needed to distinguish data provenance? If a table accepts data from multiple sources (`data_source`), the PK **must** include `data_source` — otherwise `INSERT OR REPLACE` silently overwrites rows from other sources. This is a **data corruption** risk, not just a schema style issue. See `hermes-cron-pipelines` → `references/moneyflow-pk-migration.md` for a concrete fix.

#### 🔴 Check 2: Date Format Compatibility (Pipeline Integrity)

This is the #1 silent-failure class in multi-source data pipelines.

```python
# Identify every place a date is:
#   - Read from DB (daily_kline stores YYYYMMDD? daily_factors stores YYYY-MM-DD?)
#   - Written to DB
#   - Compared with another date column
#   - Passed as a parameter to a query
#   - Used in a pandas merge/join on date

# Red flags:
#   .replace("-", "")   ← explicitly stripping dashes
#   strptime / strftime  ← transforming format
#   empty template: f"{s[:4]}-{s[4:6]}-{s[6:8]}"  ← format conversion needed
#   merge/join on 'date' with how='left' without format check
```

**Mitigation:**
- A single `_normalize_date()` / `ensure_iso_date()` function should exist and be called before every merge
- After a merge on date, ALWAYS assert `merged['key_column'].notna().sum() > 0.8 * len(merged)`
- Document the date format convention per table as a comment near the DDL

#### 🔴 Check 3: Default Value Risk (Silent Condition Bypass)

Default values for missing data can silently alter strategy behavior.

```python
# Patterns to find:
#   .fillna(100.0)      ← very high default → condition always passes
#   .fillna(1)          ← boolean default → condition always passes
#   .fillna(True)       ← boolean default → condition always passes
#   .fillna(999999)     ← out-of-range default → always passes a comparison

# Good default pattern:
#   .fillna(0)          ← safe for "> 0" checks
#   .fillna(-1)         ← safe sentinel, check with value >= 0
#   .fillna(False)      ← safe for boolean conditions
```

**Checklist:**
- Every `.fillna()` should be justified: does this default make the condition more permissive or more restrictive?
- If the strategy has N conditions and a condition's data is missing, it should FAIL NOT PASS
- After a merge/extract, log the ratio of defaults used vs real data
- Consider raising an exception when coverage < 50%

#### 🔴 Check 4: Config Drift (Declared vs Consumed)

Compare config dict keys against actual consumption sites.

```python
# grep for:
#   V4_PARAMS["xxx"]   ← keys consumed by code
#   V4_PARAMS = { ... "xxx" ... }  ← keys declared

# Any key in the dict but never referenced in code? → dead config
# Any key referenced in code by a different name? → naming drift
# Any key that should be in the dict but is hardcoded instead? → hardening opportunity
```

**Look for:**
- Strategy parameters hardcoded in function bodies when a config key exists with the same name
- Config keys sent to frontend that are never used in backtest logic (UI will show incorrect/untunable params)
- `version` key defined but never consumed for migration/audit
- copy-paste duplicates of the same default value in multiple files

#### 🔴 Check 5: Cron / Ops Infrastructure

Check that operational automation isn't silently broken.

```python
# For every cron job, verify:
#   1. The Script field references a file that EXISTS
#   2. The file is executable (shell scripts) or callable via python
#   3. The script propagates exit codes (no silent [DONE] after failure)
#   4. The script has basic error notification (exit code checked, stderr captured)
#   5. Dependent jobs are staggered (not same cron minute)
```

**Checklist:**
- `hermes cron list` to inspect all jobs
- `ls -la` on every referenced script
- Read each script: does it check `$?` or `$LASTEXITCODE`? Does it `exit $?`?
- Are there dependent data chains? (e.g., kline update → factor compute → report push). If so, are they staggered?

**Common failure modes:**
- Shell script called from cron with no shebang → silent exit 127
- Script uses `cd ~/project` but cron runs in a different environment
- `echo "[DONE]"` after python failure → misleading log
- Missing wrapper script (cron references a file that doesn't exist)

#### 🔴 Check 6: File Permissions & Existence

```bash
# For shell scripts referenced by cron:
ls -la path/to/script.sh   # should be 755 (rwx--x--x) or at least 644 with +x

# For python scripts called directly:
ls -la path/to/script.py   # 600 is fine — called via python3 script.py

# For cron wrapper scripts: must exist
find PROJECT_ROOT -name "wrapper_name.sh"   # should not be empty
```

#### 🔴 Check 7: Execution Flow / Race Conditions

For any data pipeline with multiple stages:
- Are there **write-read conflicts** where one job writes to a table while another reads it?
- Are there **order-of-operations assumptions** without explicit synchronization?
- Is the pipeline **idempotent** (re-running a day produces same result)?
- Is there a **lock/mutex** mechanism for competing writes?

#### 🟠 Check 8: Dual-Path Coverage (Table vs Fallback)

Many systems have TWO code paths for the same task — a fast table-lookup path and a slow recompute/fallback path. Fixes and features must be verified independently on BOTH.

```python
# Common dual-path patterns:
# 1. screen_from_factors()  ← table lookup (fast)
#    screen_fallback()      ← per-stock compute (slow)
# 2. load_to_dataframe()    ← from dz_dailyquote
#    pd.read_parquet()      ← fallback from parquet file
# 3. backtest_v4.py         ← uses daily_factors table
#    screen_v4.py fallback  ← calls calc_* functions directly
```

**What to check:**
- For every filter/check (ST exclusion, suspension detection, date range):
  - Does the **table path** have the logic? (SQL WHERE clause, pandas filter)
  - Does the **fallback path** have the logic? (inline check, function call)
  - Are the thresholds IDENTICAL between the two paths?
- For every data column:
  - Does the fast path get it from the precomputed table?
  - Does the fallback path compute it from the same source data?
- When you fix a bug in one path, do NOT assume it applies to the other — verify independently

**Detection script:**
```bash
# Find dual-functions by matching name patterns
grep -n "^def.*fallback\|^def.*screen_from_\|^def.*load_to_\|^def.*compute_\|^def.*_direct" *.py
# Then read BOTH functions, not just the one you think matters
```

#### 🟠 Check 9: Pipeline Sibling Comparison (Structural Mirroring)

When auditing a new pipeline, compare it against an **established reference pipeline** that serves a similar purpose / uses the same stack. This reveals defects invisible when auditing either alone.

Define comparison dimensions, then diff:

**DIMENSION 1: Shell wrapper completeness**
- Does both have `[ -f "$SCRIPT" ]` guard?
- Does both use `|| true` on piped commands (pipefail safety)?
- Does both capture `PIPESTATUS` immediately?
- Does both resolve `SCRIPT_DIR` via `${BASH_SOURCE[0]}`?

**DIMENSION 2: Date resolution strategy**
- Pipeline A: checks local `trade_cal` table first → fallback to API
- Pipeline B: always calls API with hardcoded `start_date="20260101"`
- → Inconsistency means B has unnecessary API dependency and future date-overflow risk

**DIMENSION 3: Schema usage & PK coverage**
- Pipeline A: INSERT with explicit column list, PK includes `data_source`
- Pipeline B: `INSERT OR REPLACE` on PK without `data_source`
- → Without `data_source` in PK, two pipelines silently overwrite each other's rows

**DIMENSION 4: Operational maturity**
- Retry strategy (exponential backoff? single retry? none?)
- Data-ready threshold (≥4800 rows vs ≥100 rows to consider "complete")
- Dead code present (defined constants/functions never used)?
- Field redundancy (same API value written to two DB columns)?

**DIMENSION 5: Error propagation**
- Pipeline A: error → exit → wrapper logs failure
- Pipeline B: partial write succeeds with 2% coverage → date marked "complete"

**Concrete worked example:** see `references/moneyflow-pipeline-audit-example.md` — Tushare moneyflow pipeline audited against the QFQ kline reference pipeline. Found 7+ defects including PK without data_source, missing shell pre-flight checks, and dead code.

#### 🟠 Check 10: Sibling/Clone File Integrity

When script or config files with the same name exist in MULTIPLE locations (project source vs installed copy), the active copy may drift out of sync.

```bash
# Common sibling pairs:
#   my_quant_system/scripts/daily_factor_update.sh   ← source
#   ~/.hermes/scripts/daily_factor_update.sh          ← cron's copy
#
#   scripts/qfq_import.sh                              ← source
#   ~/.hermes/scripts/qfq_import.sh                    ← cron's copy
```

**What to check:**
1. Identify all cron jobs (`hermes cron list` or `cat ~/.hermes/cron/jobs.json`)
2. For each script field, note the filename (short name)
3. Find ALL copies of that filename: `find ~/my_quant_system ~/.hermes -name "daily_factor_update.sh"`
4. Compare the active copy (the one cron actually calls) against the project source copy
5. TODO: a `diff` or structural comparison — a fix applied to the project copy but not the cron copy is NOT deployed

**Which copy does cron use?** → Hermes runs scripts from `~/.hermes/scripts/` by default (unless the cron job specifies an absolute path). If both copies exist, the `~/.hermes/scripts/` one is the live one.

**Drift indicators:**
- Different file sizes (`ls -la` both)
- Different shebang lines
- Different error handling patterns (exit code check present in one, absent in the other)
- One has `set -euo pipefail` and the other doesn't

#### 🟠 Check 11: Data Integration Plan vs Reality Verification

When reviewing a data integration plan (schema design + ETL script + API/CLI data source), verify that ALL THREE layers agree: the plan document, the implementation script, and the actual data source response.

**Workflow:**

1. **Read the plan document** — extract schema definitions, field mappings, update strategies, and CLI parameter expectations
2. **Check DB against plan** — `PRAGMA table_info(tablename)` on every target table. Do columns, types, and PKs match?
3. **Check script against plan** — do the SQL INSERT statements, collect functions, and CLI argument names implement what the plan describes?
4. **Check script against API** — test the actual CLI/API calls to see the real response format:
   - Compare API response field names against the script's `item.get(...)` calls
   - Flag every field the script maps to `None` — these are either absent from the API or the mapping is wrong
   - Verify CLI parameter names verbatim (run `--help` on the CLI, or read the argparse source; don't trust the plan doc alone)
5. **Check real DB data quality** — query for actual stored rows:
   - Count NULL rates per column: `SUM(CASE WHEN col IS NULL THEN 1 ELSE 0 END) / COUNT(*)`
   - Spot-check field values for semantic correctness (e.g., `total_amount` should differ from `buy_top_amount`; same value in both columns = copy error)
   - Check ROWID gaps — e.g., ROWID starting at 105 instead of 1 suggests a manual pre-seed followed by script append
6. **Assess operational readiness**:
   - Error handling — does `--all` / batch mode abort on first failure, or continue with error counters?
   - Retry mechanism — any exponential backoff for transient API failures?
   - Cron integration — do the shell wrappers exist in `~/.hermes/scripts/`?
   - Logging — does the script write to the pipeline's `etl_runs` table?
7. **Cross-reference stock code formats** — if the system has a watchlist table, compare its code format (bare `301338` vs suffixed `301338.SZ`). A format mismatch blocks JOIN-based filtering.

**Severity classification for findings:**

| Finding Type | Examples | Severity |
|-------------|----------|----------|
| API field absent from response but required by table | `price`, `pct_chg` nonexistent in API | 🔴 Critical — rebuild table or drop columns |
| Same API value written to two DB columns | `total_amount` = `buy_top_amount` (same `buy_value`) | 🔴 Critical — fix script mapping |
| API field exists but script doesn't map it | `seal_money` undigested → `fd_amount` stays NULL | 🔴 Critical — add field mapping |
| Code format incompatibility | watchlist bare codes vs thscode with suffix | 🟡 Medium — blocks JOIN |
| No retry / no cron shell wrappers | single-attempt API calls, no wrapper scripts in ~/.hermes/scripts/ | 🟢 Low — operational gap |
| CLI doc mismatch | plan says `--date`, CLI actually requires `--date-ms` | 🟢 Low — documentation |

**Worked example:** [`references/data-integration-plan-review.md`](references/data-integration-plan-review.md) — Financial-API fuyao → SQLite `stock_data.db` integration plan review (2026-07-05). Found 4 critical field-mapping errors, 6 medium issues, and 5 improvement suggestions.

#### 🟠 Check 12: Import & Module Hygiene

Import patterns in Python codebases are a frequent source of fragility, performance waste, and confusing runtime errors. Systematically inspect.

```python
# ❌ BAD: sys.path.insert inside a function (re-run every call)
def generate_signals(df, ...):
    if use_enhanced:
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "financial_api"))
        from signal_enhancer import enhance_buy_signal
    ...

# ❌ BAD: Per-call import inside a loop (re-run hundreds of times)
for date in all_dates:
    from signal_enhancer import dynamic_max_positions  # ← INSIDE LOOP
    ...

# ❌ BAD: Duplicate sys.path.insert from different callers for same module
# generate_signals() inserts "financial_api" to import signal_enhancer
# run_multi_backtest() does the same thing independently

# ✅ GOOD: Top-level single import with try/except guard
try:
    import signal_enhancer as _enhancer
except ImportError:
    _enhancer = None
# All call sites: if _enhancer is not None: _enhancer.xxx()
```

**Systematic inspection checklist:**

| Check | Detection | Fix |
|-------|-----------|-----|
| `sys.path.insert` in function bodies | `grep -n "sys.path.insert" *.py **/*.py` then inspect context | Hoist to module level; one path resolution per module |
| Imports inside `if`/`for` blocks | `grep -n -B3 "^\s*from \|^\s*import " *.py` then check indentation | Move to module level with `try/except ImportError` |
| Same module imported in >1 function | Cross-reference module names across function bodies | Single top-level import |
| Silent import failure + no guard | `try: import X; except: pass` without downstream `X is not None` check | Add guard or re-raise with clear message |

**Severity:**
- Import inside a loop body → **Medium** — not a correctness bug but wastes cycles, hurts readability, and signals that imports were added ad-hoc
- `sys.path.insert` inside a function → **Medium** — fragile (depends on call order), duplicated across callers
- Import silently failed + no guard → **High** — produces `AttributeError: 'NoneType' object has no attribute 'xxx'` at runtime, confusing

#### 🟠 Check 13: DB Connection Lifecycle (try/finally)

SQLite connections not wrapped in `try/finally` leak on exceptions during complex multi-day loops or batch processing.

```python
# ❌ BAD: DB open → 200 lines of logic → close at the end
conn = sqlite3.connect(path)
# ... loop with possible exceptions ...
conn.close()  # ← never reached if exception thrown midway

# ✅ GOOD: try/finally ensures cleanup
conn = sqlite3.connect(path)
try:
    # ... all logic ...
finally:
    try:
        conn.close()
    except Exception:
        pass
```

**Inspection:**
- Find every `sqlite3.connect()` call. For each: is there a `try` between `connect()` and the corresponding `close()`?
- If `close()` is at the end of a function body with no `try`, the connection leaks on any exception before that point
- Multiple connections opened independently (e.g., one in `__main__`, one inside a function) → each needs its own `try/finally`
- Python will garbage-collect the connection eventually, but not until the function's stack frame is collected, which may be never if the exception propagates to the user

#### 🟠 Check 14: SQL Aggregate NULL Handling

SQL aggregate functions (`SUM`, `AVG`, `MAX`) return `NULL` when the result set is empty (no rows match `WHERE`, or all values are `NULL`). In Python, this arrives as `None` and can silently corrupt downstream logic.

```python
# ❌ BAD: SUM returns NULL on empty table → multi_ladder = None
row = _safe_query(conn, "SELECT SUM(CASE WHEN ... THEN 1 ELSE 0 END) as multi FROM ...")
multi_ladder = row[0]["multi"] if row else 0  # row is truthy but multi is None!

# ✅ GOOD: COALESCE ensures 0, int() ensures typed
row = _safe_query(conn, "SELECT COALESCE(SUM(...), 0) as multi FROM ...")
multi_ladder = int(row[0]["multi"]) if row else 0  # now always int
```

**Why this matters:** `None` passes through arithmetic without raising (Python allows `None + 1` in numpy? depends on dtype). Downstream `if total_ladder == 0:` works accidentally, but `multi_ladder / total_ladder` with `multi_ladder=None` produces `NaN` in numpy, which then fails any comparison.

**Systematic check:**
- Every `SUM(...)`, `AVG(...)`, `MAX(...)`, `MIN(...)` without `GROUP BY` on a non-empty table — wrap in `COALESCE(..., 0)` or `COALESCE(..., 0.0)`
- In Python: after fetching, use `int(val) if val is not None else 0` or `float(val) or 0.0` rather than assuming column is never NULL
- Pay special attention to `COUNT(*)` — this never returns NULL (always 0 on empty set), but `COUNT(col)` does return NULL when all values in `col` are NULL

#### 🟠 Check 15: Default Value Risk in Backtesting Conditions

Defaults for missing data can silently make strategy conditions pass, producing confidently wrong backtest results. A variant of Check 3 specialized for quant code.

```python
# ❌ BAD: fillna with permissive defaults
df['zhuli_holding'] = df['zhuli_holding'].fillna(100.0)   # always > 20 ✓ passes
df['inflow_signal'] = df['inflow_signal'].fillna(1)        # always True ✓ passes

# These make holding_ok and inflow_ok ALWAYS pass, even when
# 90% of rows have no data. The backtest looks "working"
# but is actually buying blind.

# ✅ GOOD: fillna with restrictive defaults
df['zhuli_holding'] = df['zhuli_holding'].fillna(0.0)      # never > 20 ✗ fails
df['inflow_signal'] = df['inflow_signal'].fillna(0)         # never True ✗ fails

# ✅ BETTER: log default coverage ratio, warn if > 50%
```

**When to flag:**
- `fillna` on a column feeding a `> threshold` condition: is the default ABOVE or BELOW the threshold?
- If ABOVE (permissive), data gaps widen the strategy instead of narrowing — **this is a bug** unless explicitly documented
- If BELOW (restrictive), data gaps shrink the strategy — conservative and acceptable
- After every merge/extract on a strategy data column, assert or log the ratio of defaults used vs real data

#### 🟢 Check 16: Docstring ↔ Implementation Drift

Docstrings describing different behavior than the code causes confusion and trust erosion.

```python
# ❌ BAD: docstring says one thing, code does another
def dynamic_max_positions(..., default_max=3):
    """
    规则:
      - 其他情况 → 默认（2只）
    参数:
      default_max: 默认最大持仓数（无数据时返回）
    """
    # docstring says "默认（2只）" but default_max=3
    # docstring says "无数据时返回" which is correct,
    # but first sentence implies middle case should return default_max
```

**Inspection:**
- For every `default=`, `kwargs.get("key", DEFAULT_VAL)`, or fallback pattern: does the docstring match?
- Pay attention to: threshold descriptions, default value claims, return value ranges
- Check that parameter **names** in docstring match actual parameter names (e.g. `default_max` vs `default_max_positions`)
- The most common drift: a parameter that once had a certain default was changed but the docstring wasn't updated

### Step 4 — Severity Rating

Rate each finding:

| Rating | Label | Meaning | Action |
|--------|-------|---------|--------|
| 🔴 A | Critical | Bug that silently produces wrong results or blocks execution | Fix immediately |
| ⚠️ C | Medium | Config drift, missing fallbacks, weak defaults | Fix this week |
| ⚠️ D | Low | Redundant checks, minor timing concerns | Monitor |
| ✅ A | None | No issues | Pass |

### Step 5 — Output Format

Always present findings as a **table** with severity, file location, description, and recommended fix. Follow findings with a prioritized remediation list.

A worked example of dual-path audit and sibling-script drift (from a production fix-verification session) exists at `skill_view(name="codebase-quality-review", file_path="references/fix-audit-dual-path-drift.md")`.

## Pitfalls

- **Date format blind spot**: This is the most common silent failure in multi-source systems. Always check date formats across every table. Do not assume `YYYY-MM-DD`.
- **Silent fillna**: Default values that make conditions pass are worse than missing data — they produce confident wrong results.
- **Configuration theater**: A config file whose values are not consumed by the runtime appears well-architected but is actually dead code.
- **Missing cron scripts**: Cron tasks that reference nonexistent files run silently. Always verify the Script path with `ls`.
- **Parallel cron at same minute**: Two cron tasks at the same time that share a DB table can produce partial-read races. Stagger by at least 10 minutes.
- **Stub functions that look real**: A function with a docstring, type hints, and `return df` at the end may do nothing. `filter_suspended(df)` that returns df without filtering is indistinguishable from a real function in a surface scan. Check: does the function body actually call any filtering logic (`.drop`, `.isin`, `df[~...]`, `continue`), or does it just pass through? Functions ending in `return df` with no intermediate mutation are suspicious.
- **Quant system ops risk assessment**: For a holistic audit of a running quant system's operational reliability (beyond code quality into SQLite performance, backup integrity, Hermes cron restart resilience, chain dependency risks, and data quality/checksum coverage), see `references/quant-system-ops-risk-assessment.md`.
