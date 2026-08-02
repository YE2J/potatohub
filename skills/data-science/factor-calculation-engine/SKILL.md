---
name: factor-calculation-engine
description: "Design and build a batch factor calculation engine for A-share stocks: mass SQL loading, per-stock vectorized computation, checkpoint/resume, parallel execution, and extensible factor registry. Covers the layer between data ingestion and strategy/backtesting."
version: 1.3.0
author: Hermes Agent
tags: [a-share, factor-calculation, batch-processing, parallel, checkpoint, sqlite, quant]
platforms: [macos, linux]
---

# Factor Calculation Engine

批量化因子计算引擎设计。覆盖 A 股全市场（5,000+ 只）的因子计算管线：批量 SQL 加载、逐只向量化计算、断点续传、并行加速、可扩展因子注册。

## When to Use

- 用户需要全市场（或数千只股票）的因子扫描/筛选
- 用户提到"批量化"、"性能优化"、"错误恢复"、"断点续传"
- 需要在现有 `daily_kline` + `moneyflow_daily` 数据上运行多因子计算
- 需要设计可扩展的因子架构（新增因子时改动最小）
- 现有 `screen_v4.py` 之类的单线程 N+1 循环已成为性能瓶颈
- 需要写 `strategy_library/factors.py` 模块或 `scripts/import_daily_factors.py` CLI

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                      Factor Engine                          │
├─────────────────────────────────────────────────────────────┤
│  DataLoader ──→ FactorPipeline ──→ ResultWriter              │
│  (2x SQL)       (逐只计算)         (事务批量写入)              │
│       │               │                  │                   │
│       ▼               ▼                  ▼                   │
│   stock_data.db    Checkpoint        stock_data.db           │
│                    Manager            / factor_results       │
└─────────────────────────────────────────────────────────────┘
```

### Three-Phase Pipeline

| Phase | 操作 | 效果 |
|-------|------|------|
| **Phase 1** | 2次SQL批量加载全部K线+资金流 | N+1 (10,370次) → 2次SQL (-99.98%) |
| **Phase 2** | 逐只因子计算 (并行) | 错误隔离 + 断点续传 |
| **Phase 3** | 事务批量写入 daily_factors 表 | 支持查询和回测 |

## Implemented Modules

Two modules now exist in production:

### `strategy_library/factors.py` — 因子表管理模块

Six public functions:

| Function | Purpose |
|---|---|
| `ensure_schema(db_path)` | Execute `factor_ddl.sql` to create 4 tables |
| `batch_load_data(db_path, start, end)` | 2-SQL bulk loader → `{secu_code: {kline, moneyflow}}` |
| `compute_factors(stock_code, kline, mf)` | Call 5 real indicators → 15-factor dict for last day |
| `batch_compute_and_write(stock_data, date, db_path)` | Per-stock loop + upsert executemany (500/batch) |
| `query_factors(db_path, date, conditions)` | Filtered query |
| `get_factor_history(db_path, stock, start, end)` | Time series for one stock |

Key patterns:
- **FACTOR_FIELDS** — a list of 15 field names, source-of-truth for both SQL generation and result dicts
- **UPSERT_SQL** — dynamically built from FACTOR_FIELDS: `INSERT OR REPLACE INTO daily_factors (...) VALUES (...)`
- **Per-factor error isolation** — 5 separate try/except blocks, each catches its own factor. One factor failing does NOT skip the stock
- **Column mapping** — `radar_buy_signal→radar_buy`, `ai_activity→ai_score`, `ai_activity_breakout→ai_strong`
- **Date normalization** — `_normalize_date()` handles both `20260626` and `2026-06-26` formats
- **InnerCode↔SecuCode** — via `all_ashare_stocks.csv` mapping
- **MoneyflowAdapter** — `_map_to_ths_columns()` converts DB columns to THS variable names
- **MONEY injection** — after mapping, repair `MONEY` column from actual kline `amount` data
- **checksum** — SHA256 of concatenated factor values (first 16 hex chars per row)

### `scripts/import_daily_factors.py` — CLI 入口

Four subcommands:

| Command | Purpose |
|---|---|
| `init` | Create schema + register 6 factor_meta entries |
| `daily --date YYYY-MM-DD` | 120-day window → compute → write → run_log |
| `backfill --start S --end E` | 60-day chunks, checkpoint resume via run_log |
| `validate --date YYYY-MM-DD` | Coverage, NULL%, outlier → factor_data_quality |

## Workflow

### 1. Batch Data Loading

Replace N+1 SQL pattern with 2 bulk queries:

```python
def load_batch_data(db_path: str, kline_start: str, mf_start: str):
    """Only 2 SQL queries for the entire market."""
    conn = sqlite3.connect(db_path)
    
    # SQL 1/2 — ALL kline data from all stocks
    kline_all = pd.read_sql(
        "SELECT stock_code, date, open, high, low, close, volume, amount "
        "FROM daily_kline ORDER BY stock_code, date", conn
    )
    kline_all = normalize_date_format(kline_all)
    kline_all = kline_all[kline_all['date'] >= kline_start]
    
    # SQL 2/2 — ALL THS moneyflow data
    mf_all = pd.read_sql(
        "SELECT stock_code, date, elg_buy_amt, elg_sell_amt, ... "
        "FROM moneyflow_daily WHERE date >= ? AND data_source='ths' "
        "ORDER BY stock_code, date", conn, params=(mf_start,)
    )
    conn.close()
    
    # Split into per-stock dicts (zero-copy via GroupBy)
    kline_map = dict(tuple(kline_all.groupby('stock_code')))
    mf_map = dict(tuple(mf_all.groupby('stock_code')))
    return kline_map, mf_map
```

Memory: ~155 MB steady state for ~5,200 stocks (649K kline rows + 207K moneyflow rows).

### 2. Per-Stock Factor Pipeline

```python
class FactorPipeline:
    def run_single(self, code: str, kf: pd.DataFrame, mf: pd.DataFrame) -> Dict:
        result = {'stock_code': code, 'calc_duration_ms': 0}
        t0 = time.perf_counter()
        
        if len(kf) < 30:  # Minimal data requirement
            return {'stock_code': code, 'error': 'insufficient_kline'}
        
        # Stage 1: OHLCV-only factors (no moneyflow needed)
        try:
            df = calc_zhuli_radar(kf)
            df = calc_gs_signal(df)
            df = calc_ai_activity(df)
        except Exception as e:
            return {'stock_code': code, 'error': f'stage1: {e}'}
        
        # Stage 2: Moneyflow-dependent factors
        if len(mf) > 0:
            merged = merge_moneyflow(df, mf)
            try:
                df = calc_dark_pool(merged)
                df = calc_zhuli_holdings(merged)
            except Exception as e:
                return {'stock_code': code, 'error': f'stage2: {e}'}
        
        # Extract target-date values
        result.update(extract_latest_signals(df))
        result['calc_duration_ms'] = int((time.perf_counter() - t0) * 1000)
        return result
```

### 3. Checkpoint & Resume (断点续传)

```python
class CheckpointManager:
    def __init__(self, run_id):
        self.completed = set()
        self.path = f"checkpoints/factor_run_{run_id}.json"
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        self._load()
    
    def _load(self):
        if os.path.exists(self.path):
            with open(self.path) as f:
                self.completed = set(json.load(f).get('completed_codes', []))
    
    def mark_done(self, code):
        self.completed.add(code)
    
    def save(self, force=False):
        if not force and len(self.completed) % 100 != 0:
            return
        with tempfile.NamedTemporaryFile(mode='w', dir=os.path.dirname(self.path),
                                         delete=False) as f:
            json.dump({
                'run_id': self.run_id,
                'completed_codes': list(self.completed),
                'total': len(self.completed),
            }, f)
        os.replace(f.name, self.path)  # Atomic swap
    
    def skip_completed(self, items):
        remaining = [s for s in items if s[0] not in self.completed]
        return remaining
```

### 4. Parallel Execution

```python
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing

def run_parallel(pipeline, stock_items, kline_map, mf_map, max_workers=None):
    pool = ProcessPoolExecutor(max_workers=max_workers or multiprocessing.cpu_count() - 1)
    total = len(stock_items)
    
    # Submit all jobs
    future_map = {
        pool.submit(_run_single, code, kline_map, mf_map): idx
        for idx, (code, *_) in enumerate(stock_items)
    }
    
    results = [None] * total
    for future in as_completed(future_map):
        idx = future_map[future]
        results[idx] = future.result()  # error handled inside _run_single
    
    return [r for r in results if r]
```

**Why not ThreadPoolExecutor?** — Factor functions use numpy/pandas which release the GIL minimally. Process pool gives true parallelism.

### 5. Batch DB Write

```python
def write_batch(conn, results, calc_date, run_id, batch_size=500):
    now = datetime.now().isoformat()
    for i in range(0, len(results), batch_size):
        batch = results[i:i+batch_size]
        with conn:  # auto-transaction
            conn.executemany("""
                INSERT OR REPLACE INTO factor_results
                (stock_code, calc_date, run_id, updated_at,
                 gs_g_point, gs_bull_market, gs_zj,
                 radar_zhuli, radar_sanhu, ai_activity,
                 dark_pool_1d, zhuli_holding,
                 signal_strength, signal_buy,
                 calc_duration_ms, error_msg)
                VALUES (?,?,?,?, ?,?,?, ?,?,?, ?,?, ?,?, ?,?)
            """, [extract_row(r, calc_date, run_id, now) for r in batch])
```

### 6. Extensible Factor Registry

```python
FACTOR_REGISTRY = {
    'gs_signal': {
        'func': calc_gs_signal,
        'stage': 1,                    # OHLCV-only
        'requires': ['close','open','high','low'],
        'outputs': ['gs_g_point','gs_bull_market','gs_zj'],
    },
    'zhuli_radar': {
        'func': calc_zhuli_radar,
        'stage': 1,
        'requires': ['close','open','high','low','volume'],
        'outputs': ['radar_zhuli','radar_sanhu','radar_buy_signal'],
    },
    'dark_pool': {
        'func': calc_dark_pool,
        'stage': 2,                    # Needs moneyflow
        'requires': ['close','open','high','low','volume',
                     'elg_buy_amt','elg_sell_amt','lg_buy_amt','lg_sell_amt'],
        'outputs': ['dark_pool_1d','dark_pool_3d','dark_pool_5d'],
    },
}
```

To add a new factor: ① write `calc_xxx(df) → df` ② register in FACTOR_REGISTRY ③ add columns to `factor_results` table ④ add mapping in `write_batch()`.

## Performance Estimates

### Single-Day Computation (5,200 stocks)

| Metric | Before (screen_v4.py) | After (engine) |
|--------|----------------------|----------------|
| SQL queries | 10,370 | 2 |
| Total time (5,200 stocks) | ~10 min | ~30-60s |
| CPU utilization | <20% (single-thread) | ~300% (4 workers) |
| Error visibility | `except: continue` (black box) | Structured log + per-stock errors |
| Crash recovery | Full re-run | Resume from checkpoint (~3s) |
| Memory | ~350 MB peak | ~155 MB steady state |

### Historical Backfill (386 trading days × 5,200 stocks)

| Phase | Operation | Cost |
|-------|-----------|------|
| `batch_load_data()` | 2× SQL: 130-day window kline + moneyflow | ~3-5s/day |
| `compute_factors()` | 5 indicators per stock (numpy + for-loop) | ~8-15s/day |
| `batch_compute_and_write()` | UPSERT 5,200 rows (500-row batches) | ~2-3s/day |
| **Single day total** | | **~15-25s** |
| **Full backfill (serial)** | 386 days | **~2.1 hours** |
| **Full backfill (8 workers)** | Parallel | **~16 minutes** |
| **DB write volume** | 386 days × 5,200 rows × 176 bytes/row | **~350 MB** |

### Data Window Requirements

| Indicator | Max Rolling Window | History Needed |
|-----------|-------------------|:------------:|
| calc_gs_signal | EMA(close,99) + MA(close,27) + SUM(C,26) | **99 days** for EMA_99 convergence |
| calc_zhuli_radar | SMA(13) + SUM(26) + MA(11) | 26 days |
| calc_ai_activity | COUNT(10) + HHV/LLV(2) | 10 days |
| calc_dark_pool | REF(C,1), moneyflow merge | 1 day |
| calc_zhuli_holdings | Full sequence for-loop from i=0 | **Entire available history** |
| cross_zero | REF(radar_zhuli, 1) | 1 day |

⚠️ **GS signal's EMA_99 needs 99+ data points** for the bull/bear line to converge. The backfill uses a 130-calendar-day window (~90 trading days), which **barely covers** this. Before convergence the formula has a fallback (`np.where(np.isnan(BB0), bb1, BB0)`) that keeps other signals alive, but `gs_bull_market` accuracy improves with a longer window.

## Database Schema for Results

The implementation uses `daily_factors` table (defined in `factor_engine/factor_ddl.sql`) with this structure:

```sql
CREATE TABLE IF NOT EXISTS daily_factors (
    stock_code     TEXT NOT NULL,
    trade_date     TEXT NOT NULL,
    gs_g_point     REAL,   -- GS信号G点 (0/1)
    gs_bull_market REAL,   -- GS牛市信号 (0/1)
    gs_tcy         REAL,   -- GS趋势延续信号
    gs_tkc         REAL,   -- GS突破信号
    radar_zhuli    REAL,   -- 主力强度 [-100,100]
    radar_sanhu    REAL,   -- 散户强度 [-100,100]
    radar_maisell  REAL,   -- 买卖比 (0~30)
    radar_buy      REAL,   -- 买入信号 (0/1)
    ai_score       REAL,   -- AI活跃度评分 [0,100]
    ai_strong      REAL,   -- AI强势信号 (0/1)
    dark_pool_1d   REAL,   -- 暗盘1日净额（元）
    dark_pool_inflow_signal REAL, -- 暗盘流入信号 (0/1)
    zhuli_holding  REAL,   -- 主力持仓估算值（元）
    zhuli_ddx_daily REAL,  -- 当日DDX (%)
    cross_zero     REAL,   -- 主力线上穿零轴 (0/1)
    data_version   TEXT NOT NULL DEFAULT 'v1',
    computed_at    TEXT NOT NULL DEFAULT (datetime('now')),
    checksum       TEXT,
    PRIMARY KEY (stock_code, trade_date)
);
```

### Column Mapping: Indicator Output → DDL Column

| Indicator Output | DDL Column | Notes |
|---|---|---|
| `gs_g_point` | `gs_g_point` | Direct |
| `gs_bull_market` | `gs_bull_market` | Boolean→0/1 |
| `gs_tcy` | `gs_tcy` | Boolean→0/1 |
| `gs_tkc` | `gs_tkc` | Boolean→0/1 |
| `radar_zhuli` | `radar_zhuli` | Direct |
| `radar_sanhu` | `radar_sanhu` | Direct |
| `radar_maisell` | `radar_maisell` | Direct |
| `radar_buy_signal` | `radar_buy` | **Renamed** in `compute_factors()` |
| `ai_activity` | `ai_score` | **Renamed** in `compute_factors()` |
| `ai_activity_breakout` | `ai_strong` | **Renamed** |
| `dark_pool_1d` | `dark_pool_1d` | Direct |
| `dark_pool_inflow_signal` | `dark_pool_inflow_signal` | Boolean→0/1 |
| `zhuli_holding` | `zhuli_holding` | Direct |
| `zhuli_ddx_daily` | `zhuli_ddx_daily` | Direct |
| — | `cross_zero` | Computed from radar_zhuli[t-1]→[t]

## Data Integrity Audits

Before trusting factor output, run the comprehensive audit checklist in `references/data-integrity-audit.md`. The 10 audit categories cover: date format consistency, InnerCode mapping completeness, amount=0 propagation, moneyflow code format, data_version semantics, checkpoint safety, recursion convergence, and stock count drift.

## Pitfalls

### ⚠️ `daily_kline` Has Two Date Formats

The table stores dates in **two inconsistent formats**:

- Old data (watchlist only, ~142 stocks): `"20260105"` (YYYYMMDD, no hyphens)
- New data (full market, ~5,200 stocks): `"2026-06-15"` (ISO, with hyphens)

Using `WHERE date >= "2026-01-01"` in SQL will **silently miss** the old-format data because string comparison treats `"20260105"` as less than `"2026-01-01"`. The fix is to load all data and normalize in Python:

```python
def normalize_date_format(df: pd.DataFrame, col: str = 'date') -> pd.DataFrame:
    s = df[col].astype(str)
    has_hyphen = s.str.contains('-')
    df = df.copy()
    df.loc[~has_hyphen, col] = (
        s[~has_hyphen].str[:4] + '-' + 
        s[~has_hyphen].str[4:6] + '-' + 
        s[~has_hyphen].str[6:8]
    )
    return df
```

### Performance Myths

- **The bottleneck is I/O, not computation.** After batching, the hottest spot shifts to `calc_zhuli_holdings`'s Python for-loop (468K iterations/day for a 386-day backfill). The other 4 indicators are fully numpy-vectorized (~2.3ms per stock). Batch SQL alone reduces 10 min → ~2 min. Adding ProcessPoolExecutor(4) gets it to ~30s. Start with batch SQL, add parallelism when needed.
- **GroupBy is zero-copy (shallow).** `dict(tuple(df.groupby('stock_code')))` shares the underlying numpy arrays. It does NOT duplicate 155 MB of data.

### Error Isolation

Three layers, in order of execution:

1. **Per-stock**: `try/except` around each stock's pipeline → log → continue (never `except: pass`)
2. **Per-batch**: Retry failed batches up to 3 times (for transient DB/serialization issues)
3. **Global**: `signal.signal(signal.SIGINT, save_and_exit)` — on Ctrl+C, save checkpoint before exiting

### Memory During `pd.read_sql`

`pd.read_sql` temporarily allocates **~2-3x** the final DataFrame size during deserialization (SQLite C API → Python objects → numpy arrays). Peak during loading is ~350 MB for kline data, ~100 MB for moneyflow. This settles to ~155 MB after the groupby. This is acceptable on any machine with ≥8 GB RAM.

### Checkpoint Atomicity

Always write to a `.tmp` file first, then `os.replace()` to the final path. This prevents partial checkpoint files on crash.

### ⚠️ InnerCode Mapping Must Be Bidirectional

`daily_kline.stock_code` may store **both** InnerCodes (e.g. `66353`) and SecuCodes (e.g. `601949`) for the same stock. The `inner_to_secu` dictionary only covers InnerCode→SecuCode. Stocks stored as SecuCode get `NaN` and are `dropna`'ed.

**Symptoms**: daily_factors has 5,000 stocks when kline has 10,000+ distinct codes. ~5,000 codes silently dropped.

**Fix**: Always try both directions:
```python
kline_df["secu_code"] = kline_df["stock_code"].map(inner_to_secu)
unmapped = kline_df["secu_code"].isna()
kline_df.loc[unmapped, "secu_code"] = kline_df.loc[unmapped, "stock_code"]
```

### ✅ IC Analyzer JOIN 已修复（2026-07-02）\n\n已添加 InnerCode→SecuCode 映射，2024 年 130 天 × 5,000 只股票可用。

The `ic_analyzer._load_kline()` function reads `daily_kline` stock codes as-is, but `daily_factors` stores **6-digit SecuCodes** (after mapping). When `load_data()` LEFT JOINs on `stock_code`, it silently misses 97-99% of stocks.

**Quantified impact** (live audit of this system):

| Date | daily_factors stocks | After JOIN with kline close | Match rate |
|------|---------------------|----------------------------|------------|
| 2024-06-03 | 5,033 | **16** | 0.3% |
| 2026-06-24 | 5,206 | **142** (8-digit watchlist) | 2.7% |

The 8-digit format (YYYYMMDD, 2025-12-15 onwards) covers 147 watchlist stocks. The 10-digit format (YYYY-MM-DD) covers 10,000+ stocks but uses InnerCodes. IC analysis can only use 3 days (2026-06-24/25/26) with ~142 stocks each. **135 days of 2024 data are invisible to IC analysis** despite daily_factors having them.

**Diagnostic query to verify**:
```sql
-- Per date: how many daily_factors stocks have matching close in daily_kline?
SELECT f.trade_date, COUNT(*) as factor_stocks,
  SUM(CASE WHEN k.close IS NOT NULL THEN 1 ELSE 0 END) as has_close,
  SUM(CASE WHEN k.close IS NULL THEN 1 ELSE 0 END) as no_close
FROM daily_factors f
LEFT JOIN daily_kline k ON f.stock_code = k.stock_code
  AND (f.trade_date = k.date OR f.trade_date = REPLACE(k.date, '-', ''))
WHERE f.trade_date IN ('2024-06-03', '2026-06-24')
GROUP BY f.trade_date;
```

**Fix**: Apply InnerCode→SecuCode mapping in `_load_kline()` exactly as `batch_load_data()` does:

```python
def _load_kline(conn, start_date, end_date, stock_codes=None, inner_to_secu_map=None):
    # ... load raw kline data ...
    if inner_to_secu_map:
        df["stock_code"] = df["stock_code"].astype(str).map(inner_to_secu_map)
        unmapped = df["stock_code"].isna()
        df.loc[unmapped, "stock_code"] = df.loc[unmapped, "stock_code_orig"]
        df = df[df["stock_code"].str.match(r'^\d{6}$', na=False)]
    # Normalize dates in Python (not SQL) to handle mixed formats
    df["trade_date"] = pd.to_datetime(df["trade_date"], format="mixed")
    return df
```

Also fix the JOIN: `daily_factors.trade_date` uses `YYYY-MM-DD` while `daily_kline.date` may be either format. Use `REPLACE(f.trade_date, '-', '') = k.date` or normalize both sides before the merge.

### ⚠️ Moneyflow stock_code Suffix Stripping

`moneyflow_daily.stock_code` may have `.SH` / `.SZ` / `.BJ` suffixes coexisting with pure 6-digit codes. When intersecting `secu_in_kline` (pure 6-digit) with `secu_in_mf` (mixed), suffixed codes don't match.

**Fix**: Strip suffixes immediately after loading moneyflow data:
```python
mf_df["stock_code"] = mf_df["stock_code"].str.replace(r'\.(SH|SZ|BJ)$', '', regex=True)
```

### ⚠️ `_get_trading_days` GLOB Filter Can Miss Dates

`import_daily_factors.py:_get_trading_days()` filters `stock_code GLOB '[036]*'` on the `daily_kline` table. This only catches codes starting with 0/3/6. If `daily_kline` uses InnerCodes (which often don't start with 0/3/6), the inner join with a date that only has '9xxx' stocks will return zero dates.

**When it fails**: Days where only 北交所 (920xxx) or 三板 (4xxx/8xxx) stocks trade. Rare for A-share indices but can cause an empty trading-day list if the filter is too aggressive.

**Fix**: Remove the GLOB filter entirely — `SELECT DISTINCT date FROM daily_kline WHERE date >= ? AND date <= ?` is sufficient.

### ⚠️ `data_version` Hard-coded = "v1"

Both `batch_compute_and_write()` and CLI subcommands hard-code `version = "v1"`. This is opaque — no way to distinguish today's output from a version computed with a different indicator algorithm.

**Also**: `factor_meta.updated_at` is **only set at `cmd_init` time and never updated during runtime**. It cannot be used to detect whether the calculation code has changed.

**Fix**: Use a semver + date scheme (`v1.0.0-YYYYMMDD`) or derive the hash from the factor registry. At minimum, bump it when indicators change. For meta tracking, write the current run version to `factor_run_log.version`.

### ⚠️ `cross_zero` Silently Collapses When calc_zhuli_radar Fails

```python
# In compute_factors():
try:
    radar = calc_zhuli_radar(df)
    radar_enriched = radar
except:
    radar_enriched = df  # <-- NO "radar_zhuli" column
# Later:
zhuli_series = radar_enriched.get("radar_zhuli", pd.Series([np.nan]))
# → always NaN, cross_zero always NULL
```

**Fix**: Create a NaN placeholder column in the except block so cross_zero can properly report NULL rather than silently depending on a column that doesn't exist.

### ⚠️ Backfill Resume Lacks Row-Count Validation

`_get_completed_dates()` uses `SELECT DISTINCT trade_date FROM daily_factors` — any row existing marks the date done. If the process crashes mid-batch, the date is partially written but marked complete.

**Fix**: Validate row count against expected stock count:
```python
def _is_date_complete(conn, date, expected):
    actual = conn.execute(
        "SELECT COUNT(*) FROM daily_factors WHERE trade_date=?", (date,)
    ).fetchone()[0]
    return actual >= expected
```

### ⚠️ SQL Date Comparison Depends on Character Ordering

When `daily_kline.date` contains mixed `YYYYMMDD` and `YYYY-MM-DD` formats, SQLite comparisons like `date >= '2024-01-01'` work *by accident* because `0` (ASCII 48) > `-` (ASCII 45) makes `20240101 > 2024-01-01`. This is fragile — if all dates were `YYYYMMDD` without any `YYYY-MM-DD` rows to set the ordering context, the comparison would still work, but **if the system ever normalizes all dates to one format, the comparison behavior changes**.

**Fix**: Normalize dates at the SQL level with `REPLACE(date, '-', '')` in all WHERE clauses, or ensure a single canonical format at import time.

### ⚠️ `calc_zhuli_holdings` Has a Non-Vectorized For-Loop

This is the **single hottest spot** in the pipeline. Unlike the other 4 indicators (fully numpy-vectorized), `calc_zhuli_holdings` contains:

```python
LOOKBACK, INIT_HOLD, SCALE = 20, 15.0, 0.5
HOLD_MIN, HOLD_MAX = 2.08, 97.18
ret = np.full(n, INIT_HOLD)
for i in range(n):
    start = max(0, i - LOOKBACK)
    window = DDX[start:i + 1]
    std = np.std(window) if len(window) > 1 else 1.0
    ddx_norm = DDX[i] / max(std, 1e-6)
    if i > 0:
        raw = ret[i - 1] + ddx_norm * SCALE
        ret[i] = np.clip(raw, HOLD_MIN, HOLD_MAX)
```

The standardization step (`np.std(window)`) adds per-iteration overhead beyond the simple递推. At 5,200 stocks × 90 rows = 468K iterations/day, this adds ~1.3s per daily run. During a 386-day backfill that's **~8.4 minutes** of pure Python loop overhead. Options:
- Numba JIT (`@njit`) on the loop function
- Cython `.pyx` file
- Accept: at ~2.7µs/iteration it's tolerable

#### Calibration History
- v1 (original): `INIT=50, decay=0.1` — absolute DDX, no standardization → severe bias (~38pp on 蜀道装备)
- v2 (current): `INIT=15, SCALE=0.5, LOOKBACK=20` — rolling standardized DDX → 蜀道装备 error <0.4pp ✅
- Known limitation: SCALE is stock-dependent. 天华新能 needs SCALE<<0.5 (error 9pp at 0.5). Different DDX amplitudes across stocks prevent a single universal SCALE.
- See `a-share-factor-ic-evaluation` skill's calibration-data.md for fitting methodology.

## User Workflow Preferences

- **Get it working first, optimize later** — batch SQL is the only essential optimization. Parallelism, checkpoint, and the registry are incremental.
- **Prefer silent skip over partial data** — errors should be logged and aggregated in a final report, not dumped inline during the run.
- **Measure before optimizing** — use `time.perf_counter()` around each phase and report P50/P95 in the summary.
- **Backfill gap analysis should include data dependency validation** — check daily_kline + moneyflow_daily coverage for the full gap range before running.

## References

- Full design document: `~/my_quant_system/docs/factor_engine_design.md` (~33KB, 907 lines)
- **Concrete implementation**: `~/my_quant_system/strategy_library/factors.py` (460 lines, 6 functions)
- **CLI entry point**: `~/my_quant_system/scripts/import_daily_factors.py` (310 lines, 4 commands)
- DDL: `~/my_quant_system/factor_engine/factor_ddl.sql` (179 lines, 4 tables)
- Current screen implementation: `~/my_quant_system/screen_v4.py` (baseline for perf comparison)
- Factor functions: `~/my_quant_system/strategy_library/indicators/`
- Moneyflow adapter: `~/my_quant_system/strategy_library/adapters/moneyflow.py`
- TDX core functions: `~/my_quant_system/strategy_library/_core.py`
- Stock mapping: `~/my_quant_system/all_ashare_stocks.csv` (InnerCode↔SecuCode)
- Column mapping reference: this skill's `references/column-mapping.md`
- **Data integrity audit checklist**: this skill's `references/data-integrity-audit.md` — 10 categories covering date formats, InnerCode mapping, amount=0 repair, moneyflow formats, versioning, checkpoint safety, and stock count analysis
- **Backfill performance analysis**: this skill's `references/backfill-performance-analysis.md` — detailed gap breakdown, per-indicator window requirements, factor_meta.updated_at semantics, serial vs parallel cost estimates, DB write volume
- **Data coverage diagnostic methodology**: this skill's `references/data-coverage-diagnostic-methodology.md` — 7-step systematic protocol for JOIN failure diagnosis, including decision tree and diagnostic SQL queries
- **Alternative data sources for factor mining**: this skill's `references/alternative-data-sources.md` — Financial-API (同花顺官方) endpoints for 涨停/异动/龙虎榜/热榜 data, a-share-skill integration, and GitHub project evaluation criteria
