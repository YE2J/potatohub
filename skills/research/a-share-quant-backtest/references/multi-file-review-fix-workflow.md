# Multi-File Review & Fix Workflow Patterns

Captured 2026-07-02 from a P0→P2 triaged 9-issue fix session across 6 files.

## Priority Ordering Strategy

When working through a structured review output (issues grouped by severity):

| Priority | Scope | Verifiability |
|----------|-------|---------------|
| **P0 — Critical** | Correctness bugs (wrong results, silent skip, timing) | Verifiable by inspection + compile check |
| **P1 — Functional** | Missing robustness (edge cases, format compatibility) | Verifiable by loading + running |
| **P2 — Observability** | Monitoring, logging, versioning | Verifiable by grep for new output strings |

Each P0 must be **verified independently** before moving to P1 — never batch-verify P0+P1+P2 at the end.

## InnerCode↔SecuCode Bidirectional Mapping with Fallback

The system has two stock ID formats:

- **InnerCode** (pure number, e.g. `10000`) — used by `daily_kline` table
- **SecuCode** (6-digit, e.g. `000001`) — used by `moneyflow_daily`, `config.py`, all strategy code

The canonical approach:

```python
# 1. Load both directions
inner_to_secu, secu_to_inner = _load_stock_map()

# 2. For kline (may be InnerCode): try map first, fallback to raw value
kline_df["secu_code"] = kline_df["stock_code"].astype(str).map(inner_to_secu)
unmapped = kline_df[kline_df["secu_code"].isna()].copy()
unmapped["secu_code"] = unmapped["stock_code_str"]  # assume already SecuCode

# 3. For moneyflow (may be SecuCode): try reverse map, fallback to raw
mf_df["mf_secu_code"] = mf_df["stock_code_str"].map(inner_to_secu)
mf_df["mf_secu_code"] = mf_df["mf_secu_code"].fillna(mf_df["stock_code_str"])

# 4. Filter to valid 6-digit codes
kline_df = kline_df[kline_df["secu_code"].str.match(r'^\d{6}$', na=False)]
```

## Cross-Format Date Query in SQLite

`daily_kline.date` stores both `YYYY-MM-DD` and `YYYYMMDD` formats. Simple string `>=` fails.

**Fix**: Use `REPLACE(date, '-', '')` in every date WHERE clause:

```python
sql_start = start_date.replace('-', '')
sql_end = end_date.replace('-', '')

query = """
SELECT * FROM daily_kline
WHERE REPLACE(date, '-', '') >= ? AND REPLACE(date, '-', '') <= ?
ORDER BY stock_code, date
"""
```

Also normalize query params before passing them. Post-query, unify all returned dates to `YYYY-MM-DD`.

## Suspension Detection

A stock is suspended (停牌) when it has zero trading:

```python
last_k = df.iloc[-1]
volume = float(last_k.get('volume', 0))
close = float(last_k.get('close', 0))
pre_close = float(last_k.get('pre_close', 0))

is_suspended = (
    volume == 0
    and pre_close > 0
    and abs(close - pre_close) / pre_close < 0.001
)
```

Apply at the per-stock level in both screening (before computing indicators) and backtest (before generating signals).

## ST/退市 Filtering

Check the stock name from `all_ashare_stocks.csv`:

```python
def is_st_stock(name: str) -> bool:
    return 'ST' in (name or '').upper()
```

Apply after loading name_map, before printing/saving results. Also filter during backtest stock loading — skip the entire stock, don't filter per-day.

## Factor Coverage Logging in Backtest

After merging `daily_factors` into per-stock data:

```python
covered = df['zhuli_holding'].notna().sum()
total = len(df)
pct = covered / max(total, 1) * 100
print(f" 因子覆盖率: {pct:.1f}% ({covered}/{total} 天)")
if pct < 50:
    print(f" ⚠️ 因子覆盖率 < 50%，回测结果可能不可靠")
```

Track across all stocks: `total_factor_days += covered; total_trading_days += total;`
Print aggregate at end: `📊 因子覆盖区间: {total_factor_days}/{total_trading_days} 天 ({pct:.1f}%)`

## Dynamic Data Window for Fallback Mode

Hardcoded date windows (`"2026-01-01"`, `"2026-05-01"`) become stale. Compute dynamically relative to target date:

```python
dt = pd.Timestamp(target_date)
kline_start = (dt - pd.Timedelta(days=180)).strftime("%Y-%m-%d")   # indicators need ~120 days
mf_start = (dt - pd.Timedelta(days=60)).strftime("%Y-%m-%d")       # moneyflow needs ~30 days
```

Pass `kline_start` and `mf_start` to SQL queries instead of hardcoded strings.

## Key Files Referenced

- `screen_v4.py` — dual-mode screening (factor table + fallback)
- `backtest_v4.py` — multi-stock backtest engine
- `strategy_library/factors.py` — factor table management
- `scripts/import_daily_factors.py` — CLI for factor lifecycle
- `scripts/daily_factor_update.sh` — cron wrapper
- `all_ashare_stocks.csv` — InnerCode↔SecuCode↔SecuAbbr mapping
