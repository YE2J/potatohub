---
name: quant-system-architecture-evaluation
description: Evaluate the technical architecture of a quantitative trading system — hardware baseline, database performance limits, data pipeline completeness, risk matrix, phased implementation roadmap.
category: research
triggers:
  - "量化系统技术方案评估"
  - "系统架构评估"
  - "quant system evaluation"
  - "技术架构评审"
  - "系统可行性分析"
  - "量化系统性能分析"
  - "评估技术方案"
  - "architecture review"
  - "arch assessment"
  - "quant system architecture"
---

# Quant System Architecture Evaluation

Evaluate a quantitative trading system's technical architecture, data pipeline completeness, hardware adequacy, and implementation feasibility. Produces a structured chaptered report with actionable recommendations.

## Evaluation Dimensions

Produce assessments across these dimensions in parallel (batch independent reads):

### 1. Hardware Baseline Assessment

Collect actual (not assumed) hardware metrics:

| Metric | Command/Source |
|--------|---------------|
| RAM | `sysctl -n hw.memsize` (macOS) or `free -g` (Linux) |
| CPU model | `sysctl -n machdep.cpu.brand_string` (macOS) or `cat /proc/cpuinfo` (Linux) |
| Core count | `sysctl -n hw.ncpu` (macOS) or `nproc` (Linux) |
| Disk type | Check if SSD via `diskutil info /` or `lsblk -d -o rota` (0=SSD) |

**Assessment criteria:**
- 16GB+ RAM → adequate for SQLite + pandas batch processing at ~5K stock scale
- M-class Apple Silicon / modern Intel → single-threaded Python factor calc is fine
- SSD → critical for SQLite WAL mode performance

### 2. Database Architecture & Performance Analysis

**Step 2a — Schema & Table Census:**
```bash
sqlite3 stock_data.db ".tables"
# Then row counts for all major tables:
sqlite3 stock_data.db "
SELECT name, rows FROM (
  SELECT 'table_a' as name, COUNT(*) as rows FROM table_a
  UNION ALL SELECT 'table_b', COUNT(*) FROM table_b
  ...
) ORDER BY rows DESC;"
```

**Step 2b — SQLite Configuration Audit:**
```bash
for pragma in page_size page_count journal_mode cache_size synchronous; do
  sqlite3 stock_data.db "PRAGMA $pragma;"
done
```

Key thresholds to evaluate:

| Metric | Current | Target | Risk if unmet |
|--------|---------|--------|---------------|
| WAL mode | WAL | WAL | Write concurrency |
| synchronous | NORMAL/FULL | NORMAL | Write speed/crash safety tradeoff |
| cache_size | ⚠️ check | ≥256MB (−262144KB) | Large queries thrash disk; 8MB default is **severe** for >1GB DBs |
| page_size | 4096 | 4096 | Fine for financial data |
| mmap_size | not set | ≥2GB | Page cache for full-DB scans |

**Step 2c — Growth Projection:**
- Daily incremental rows per table → extrapolate to annual growth
- SQLite practical limit: ~50GB before query degradation. At current growth rate, project when this is reached
- moneyflow_daily table often the fastest-growing (daily ~60K rows; ~2200K/year)
- If minute data is collected, check retention policy (60-day rolling purge is recommended)

**Step 2d — Index Coverage Audit:**
List all indexes:
```sql
SELECT name, sql FROM sqlite_master WHERE type='index' ORDER BY name;
```
Check:
- Primary key indexes exist on all tables (auto-generated `sqlite_autoindex_*`)
- Compound indexes for the most common WHERE + ORDER BY patterns
- Date-based indexes for time-series queries
- Coverage indexes for JOIN-heavy views

### 3. Data Pipeline Completeness

Map every pipeline task by time, source, and status:

| Time | Task | Status | Data Source |
|------|------|--------|-------------|
| HH:MM | Task name | ✅/❌/⚠️ | e.g., Tushare MCP / Hermes cron |

**Checklist for each pipeline:**
- Is the cron job defined in `~/.hermes/cron/jobs.json` or system crontab?
- Does the referenced script file exist and is executable?
- Does `last_status` say "ok" or "error"?
- If "error": is it a genuine failure or a script-level false-positive (e.g., exit code 1 from a helper that still writes data)?
- Is the data actually present in the DB after the cron run?
- Are dependent tasks properly staggered (not running at the same minute)?
- Is the pipeline idempotent (re-running produces the same state)?

**Red flags:**
- cron scripts that exit with code 1 but write data → buggy exit code propagation
- Tasks with `last_status: "error"` for multiple consecutive runs → needs investigation
- Broken Python venvs (multiple `.venv.broken*` dirs) → environment drift
- Python version mismatch between venv and cron scripts (e.g., venv=3.9, cron=3.11)
- Factor engine functions marked `# TODO: implement actual algorithm` → core computation missing

### 4. Factor Engine & Strategy Assessment

Check the factor engine pipeline for:

| Component | Check |
|-----------|-------|
| Factor registration | Are all factor names and types in `FACTOR_FIELDS`? |
| Incremental mode | Does daily update work correctly? |
| Backfill mode | Does historical recalculation exist? |
| Data quality | Are there `factor_data_quality` rows? |
| IC evaluation | Does `ic_analyzer.py` work? |
| Algorithm stubs | Are there `# TODO` markers in core compute functions? |

**Critical: verify the actual factor computation chain.** If the factor pipeline has TODO stubs, factors may come from an external module or direct Tushare API. Identify the real source before making architecture decisions.

### 5. Short-Term Factor Data Source Mapping

For each proposed short-term factor, check if the underlying data already exists in the DB:

| Factor | Required Data | Existing? | Complexity |
|--------|--------------|-----------|------------|
| `funding_surge` (资金异动) | moneyflow_daily | ✅/❌ | Low |
| `north_star` (北向明星) | hsgt_moneyflow | ✅/❌ | Low |
| `board_resonance` (板块共振) | sector_moneyflow_ths | ✅/❌ | Low |
| `news_sentiment` (新闻情绪) | major_news (need new pipeline) | ⚠️ | Medium |
| `anomaly_signal` (异动信号) | daily_anomaly | ✅/❌ | Low |
| `event_density` (事件密度) | dragon_tiger_daily | ✅/❌ | Low |

### 6. Long-Term Factor Data Source Mapping

| Factor | Required Data | Existing? | Complexity |
|--------|--------------|-----------|------------|
| PE分位数 | daily_kline + EPS | ⚠️ Need EPS data | Medium |
| PB-ROE偏离 | fina_indicator | ⚠️ Need check | Medium |
| 估值安全度 | valuation_results | ✅ | Low |
| 行业PE偏离 | sw_daily/ci_daily | ✅ Tushare available | Medium |

### 7. Risk Matrix

Classify each risk with probability × impact:

| Risk | Probability | Impact | Level | Mitigation |
|------|------------|--------|-------|------------|
| Description | H/M/L | H/M/L | 🔴/🟡/🟢 | Concrete action |

Common risk classes in personal quant systems:
- **SQLite file size approaching performance threshold** (rare <50GB, but needs monitoring)
- **Factor pipeline core algorithm missing** (common in evolving systems)
- **Cron false-positive errors masking real failures** (common helper script bugs)
- **Data source API changes / deprecated endpoints** (medium-term risk with Tushare)
- **Financial indicator collection too slow at full-market scale** (API rate limits)
- **PE quantile meaningless for loss-making stocks** (~30% of A-shares)

### 8. Three-Tier Architecture Feasibility

When evaluating a proposed layered architecture, map it to the existing implicit layers:

```
Existing implicit layers:
  [Data Collection] → [Factor Calculation] → [Signal Output]
  Tushare MCP        factor_pipeline.py      IC evaluation / morning report

Proposed explicit layers:
  [Data Layer] → [Factor Layer] → [Decision Fusion]
```

For each new component being added:
1. Does it fit into an existing table, or need a new one?
2. Can it reuse the existing `factor_pipeline.py` incremental/backfill framework?
3. What's the update frequency? (daily/weekly/quarterly)
4. Is the data source already in the DB or available via Tushare MCP?

**Decision fusion layer design principles:**
- Short-term score: funds + news + momentum (daily)
- Long-term score: valuation + fundamental (weekly)
- Gate: short-term must exceed threshold before long-term is consulted
- Conflict handling: if short-term bullish but long-term bearish, reduce position size not cancel
- WARNING: weights and thresholds MUST be calibrated via backtest, not guessed. Use IC analysis to determine which factors actually predict returns.

### 9. Phase-Based Roadmap

Always propose 4 phases:

| Phase | Timeline | Scope | Verification |
|-------|----------|-------|-------------|
| Phase 1 | Immediate (1-2 days) | Fix critical issues: SQLite config, cron helper bugs, env cleanup | Verify each fix individually |
| Phase 2 | This week (3-5 days) | Implement easily-sourced short-term factors from existing data | IC analysis for each new factor |
| Phase 3 | Next week (3-5 days) | Add data-dependent long-term factors | Validate against valuation_results |
| Phase 4 | Ongoing | Minute data auxiliary, quarterly financial refresh, periodic DB maintenance | PRAGMA optimize monthly |

**Each phase must include a verification step** — IC analysis for new factors, data integrity check for new pipelines, performance benchmark for DB changes.

## Reference Files

- `references/quant-system-evaluation-full-report.md` — Complete 7-chapter evaluation of the A-share quant system on Mac Mini M4 (July 2026). Contains real SQLite thresholds, index audit, cron health check, and phased roadmap.

## Pitfalls

- **Never rely on `cron last_status` alone** — always verify actual data rows in the DB. Exit code 1 can be a log script bug, not a pipeline failure.
- **SQLite cache_size is not about memory efficiency** — the default 8MB is 1960s-level conservatism. For a multi-GB database, increase to 256MB+ unconditionally.
- **Factor pipeline TODO stubs are a red flag but not a block** — the actual computation may be delegated to an external module. Always trace the import chain.
- **PE quantile without EPS filter is misleading** — loss-making stocks (EPS≤0) produce negative PE; their percentile rank is meaningless. Filter them out.
- **Do not propose DB migration (SQLite→PostgreSQL/DuckDB) unless DB >50GB or concurrent write contention exists** — migration cost for a personal system far exceeds the benefit.
- **Python venv drift** — cron scripts often use a different Python than the project's .venv. Check shebang lines in cron wrapper scripts, not just `which python`.
- **分钟数据是存储膨胀的根源** — if minute_kline is collected for all stocks, set a rolling retention policy (e.g., 60 days). A single day of 1-min data for 5000 stocks = ~720K rows.
