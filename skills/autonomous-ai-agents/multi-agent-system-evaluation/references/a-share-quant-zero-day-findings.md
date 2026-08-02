# A-Share Quant System — Zero-Day Architecture Findings

Discovered during 2026-07-07 4-agent evaluation of the quant system at ~/my_quant_system/.

## SQLite Configuration Baseline

**DB**: 6.9GB, ~30 tables, SQLite WAL mode, Apple SSD (122GB free)
**Pre-optimization**: cache_size=2000 pages (8MB), no mmap, temp_store=FILE
**Post-optimization**: cache_size=-81920 (80MB), mmap_size=2GB, temp_store=MEMORY
**Growth rate**: ~2.5GB/year, 50GB performance inflection point ~5+ years away
**Largest tables**: moneyflow_daily (14.3M rows), daily_factors (2.85M rows), daily_kline (2.67M rows)

**PRAGMAs to set on every connection**:
```python
conn.execute("PRAGMA journal_mode=WAL")
conn.execute("PRAGMA synchronous=NORMAL")
conn.execute("PRAGMA busy_timeout=5000")
conn.execute("PRAGMA cache_size=-81920")      # 80MB
conn.execute("PRAGMA mmap_size=2147483648")    # 2GB
conn.execute("PRAGMA temp_store=MEMORY")
```

## cron_log_helper.sh macOS Bug

**File**: `~/.hermes/scripts/cron_log_helper.sh`
**Root cause**: `date +%s%3N` on macOS. `%N` (nanoseconds) does not exist in macOS `date`. Output is e.g. `17834202383N` — the letter N appended to the seconds timestamp instead of milliseconds.
**Impact**: 3 cron jobs show `last_status: "error"` even though data writes succeeded. The error is from shell integer comparison (`[ "17834202383N" -gt 0 ]`) failing on the non-numeric string.
**Fix**: Replace `date +%s%3N` with `python3 -c "import time; print(int(time.time()*1000))"` — both lines (lines 40 and 98 in current version).

## Factor Pipeline Chain (Real vs Stubs)

**Myth**: `factor_pipeline.py` has `# TODO: 实现实际算法` stub methods.
**Reality**: The stub methods in `factor_pipeline.py:FactorEngine` are **dead code**. The actual computation goes through:

```
import_daily_factors.py (cron entry point)
  → strategy_library.factors.batch_compute_and_write()
    → strategy_library.indicators.calc_gs_signal() (_gs_signal.py ✅)
    → strategy_library.indicators.calc_zhuli_radar() (_zhuli_radar.py ✅)  
    → strategy_library.indicators.calc_ai_activity() (_ai_activity.py ✅)
    → strategy_library.indicators.calc_dark_pool() (_dark_pool.py ✅)
    → strategy_library.indicators.calc_zhuli_holdings() (_zhuli_holdings.py ✅)
  → INSERT OR REPLACE INTO daily_factors
```

All 5 indicator files under `strategy_library/indicators/` have real implementations.

## Known Cron Schedule (Trading Days)

```
15:30 — 个股异动采集 (Tushare cls_stock_shock) ✅
16:00 — 涨停池 (FinancialAPI limit_up) ✅
16:05 — 连板天梯 (Tushare limit_step) ✅
17:00 — 龙虎榜 (Tushare top_list) ✅
18:00 — 前复权日线增量 (Tushare daily adj=qfq) 🟡 status=error (false positive)
18:15 — 指数日线 (Tushare index_daily) 🟡 status=error (false positive)
18:30 — 资金流向DC增量 (Tushare moneyflow_dc) 🟡 status=error (false positive)
19:00 — 因子每日更新 ✅
20:00 — 因子回填 ✅
22:00 — 市场热榜 ✅
03:00 — 每日DB备份 (新增恢复) ✅
07:02 — 晨报微信推送 (no_agent script) ✅
```

## Key Risk: Hermes Cron is Process-Bound

Hermes cron runs inside the Hermes desktop app process. When the app closes/restarts/crashes:
- Cron jobs stop immediately
- Missed windows are NOT auto-retried
- No launchd/systemd daemon fallback currently configured
- Protection: Register critical data collection in system crontab as backup

## index_daily pct_chg NULL issue

000300.SH (沪深300) has 4,616 out of 5,222 rows where pct_chg is NULL — 88.4% coverage gap.
Likely Tushare source data issue for early dates.
Fix: Compute from close/pre_close in SQL or the import script.
