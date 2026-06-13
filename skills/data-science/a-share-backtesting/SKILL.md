---
name: a-share-backtesting
description: "Build A-share quantitative backtesting systems with Backtrader + AKShare/Tencent API on macOS ARM64"
version: 1.0.0
author: Hermes Agent
tags: [backtrader, akshare, backtesting, A-share, quantitative, finance, python]
---

# A-Share Backtesting with Backtrader

Build quantitative backtesting systems for A-share stocks on macOS ARM64 (M4/M3). Covers the full pipeline: data ingestion → storage → backtesting → reporting.

## When to Use

- User asks to build an A-share backtesting system from scratch
- User wants to test a trading strategy on A-share historical data
- User needs help with backtrader, akshare, or quantstats integration
- User mentions "回测系统" (backtesting system) or "量化" (quantitative)

## Project Structure Template

```
my_quant_system/
├── config.py           # Global parameters (stock code, dates, cash, fees, risk control)
├── data_manager.py     # Data layer: download → SQLite → Parquet
├── indicators.py       # Custom backtrader indicators (SMA, EMA, ATR)
├── strategy.py         # Strategy class (signals, stop-loss, position sizing)
├── main.py             # CLI entry point: orchestrate backtest → report → store
├── requirements.txt    # Dependencies
├── stock_data.db       # SQLite database (auto-created)
├── data/parquet/       # Parquet files for fast backtrader loading
├── reports/            # QuantStats HTML reports
├── web_data/
│   └── watchlist.json  # Watchlist persistence (JSON array of {code, name})
└── app/                # FastAPI web UI (see Web UI section)
    ├── __init__.py
    ├── main.py         # FastAPI app: 9 routes, backtest API, page rendering
    ├── templates/      # Jinja2 templates (Bootstrap 5 dark theme)
    │   ├── base.html
    │   ├── index.html
    │   ├── watchlist.html
    │   ├── backtest.html
    │   └── history.html
    └── static/
        └── style.css   # Custom dark theme overrides
```

## Data Pipeline Strategy

### Primary source: akshare (EastMoney API)
```python
ak.stock_zh_a_hist(symbol='000001', period='daily', start_date='20200101', end_date='20250101', adjust='qfq')
```

### Fallback source: Tencent API
When EastMoney is unreachable (common outside mainland China), use Tencent API:
```
GET https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=sz000001,day,2020-01-01,2025-01-01,500,qfq
```

See `references/tencent-api.md` for exact format and pitfalls.

### Storage
- **SQLite** (`stock_data.db`): raw data with all columns for SQL queries
- **Parquet** (`data/parquet/{code}.parquet`): fast backtrader loading, columnar format
- Incremental update: query max date, download only missing days

## Backtrader Strategy Architecture

### Indicators (`indicators.py`)
Create wrapper classes extending `bt.Indicator`:
```python
class SMA(bt.Indicator):
    lines = ('sma',)
    params = (('period', 20),)
    def __init__(self):
        self.lines.sma = bt.indicators.SMA(self.data, period=self.p.period)
```
This provides a centralized place to add new indicators.

### Signals (`strategy.py`)
Implements in `next()`:
1. Check for pending orders → skip
2. If in position: update high → check stop-loss → trailing stop → time stop → signal exit
3. If not in position: check entry signal → buy with appropriate sizing

### Position Sizing
- **FixedSizer**: `int(cash × fixed_pct / price / 100) × 100` (round to 100 shares)
- **ATRSizer**: `cash × risk_factor / (ATR × price)` — volatility-aware

### Stop-Loss (three-layer protection)
1. **Fixed stop**: `close ≤ buy_price × (1 - stop_loss_pct)`
2. **Trailing stop**: `close ≤ peak_since_entry × (1 - trailing_pct)`
3. **Time stop**: `bars_held ≥ max_days`

## Reporting

Use QuantStats for professional HTML tear sheets:
```python
import quantstats as qs
qs.reports.html(returns_series, output='reports/report.html', title='Backtest Report')
```

Requires a daily returns `pd.Series` with `DatetimeIndex`. Extract via `bt.analyzers.TimeReturn`.

## Local Web UI

A FastAPI web interface provides browser-based access to the backtesting system.

### Tech Stack
- **FastAPI** — REST API + Jinja2 template rendering
- **Bootstrap 5** (CDN) — dark theme (`data-bs-theme="dark"`)
- **Fetch API** — frontend calls backend without page reload

### Routes

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/` | Dashboard: stats cards, latest backtest summary, quick links |
| GET | `/watchlist` | Watchlist: table with latest prices from SQLite |
| POST | `/api/watchlist/add` | Add stock `{code, name}` → `watchlist.json` |
| POST | `/api/watchlist/remove` | Remove stock `{code}` from `watchlist.json` |
| GET | `/backtest` | Backtest config form: stock selector, all params from `config.py` |
| POST | `/api/backtest/run` | Execute backtest: returns `{status, metrics, trades, report_url}` |
| GET | `/history` | Backtest history page |
| GET | `/api/history` | History JSON (from `backtest_results` table) |
| GET | `/reports/{filename}` | Serve QuantStats HTML reports |

### Starting the Server

```bash
cd my_quant_system
.venv/bin/python -m app.main
# OR
.venv/bin/uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Server runs on `http://127.0.0.1:8000`. The `--reload` flag auto-restarts on file changes.

### Backend Architecture

```
app/main.py
├── sys.path hack to import project modules (config, data_manager, strategy)
├── _read_watchlist() / _write_watchlist() — JSON file I/O
├── _get_latest_kline(code) — queries SQLite for most recent row
├── run_backtest() — full pipeline: get_data → create Cerebro → run → extract → save
│   ├── StockDataManager.get_data_for_backtrader()
│   ├── bt.Cerebro() with MyStrategy, analyzers
│   ├── run → extract metrics from analyzers
│   ├── generate quantstats HTML
│   └── _save_backtest_results() to SQLite
└── 9 routes (see table above)
```

### Templates Architecture

All templates inherit from `base.html` which provides:
- Bootstrap 5 dark theme
- Left sidebar navigation (4 items: 仪表盘, 自选股, 回测, 历史)
- Jinja2 `{% block content %}` for page content
- `request.path` auto-highlights the active nav item

Templates use **server-side rendering** for initial page data (passed via `TemplateResponse` context), and **Fetch API** for dynamic operations (add/remove watchlist, run backtest, load history).

### API Response Format (backtest)

```json
{
  "status": "ok",
  "metrics": {
    "final_value": 99255.32,
    "total_return": -0.74,
    "annual_return": -1.9,
    "sharpe_ratio": 0.0,
    "max_drawdown": 0.92,
    "win_rate": 0.0,
    "profit_loss_ratio": 0.0,
    "total_trades": 3,
    "winning_trades": 0,
    "losing_trades": 3
  },
  "trades": [],
  "report_url": "/reports/backtest_report_000001.html"
}
```

## Key Pitfalls

1. **akshare adds extra columns** — returns `'股票代码'` as a Chinese column. Must filter after rename: keep only `COLUMN_MAPPING.values()` columns.

2. **Tencent API uses sz/sh prefix** — `sz000001` for Shenzhen, `sh600519` for Shanghai. NOT `0.000001` or bare `000001`.

3. **Tencent K-line entries have optional 7th field** — some entries include a dividend/ex-rights dict at position [6]. Always slice to first 6 fields only.

4. **Tencent API caps at 500 entries** — if you need more history, make multiple calls with offset dates.

5. **Backtrader needs warmup** — indicators need enough bars before producing values. Check `len(self) >= period` in `next()`.

6. **Sizer override** — if strategy calls `self.setsizer()` in `__init__`, it overrides `cerebro.addsizer()`. Pick one approach, not both.

7. **Backtrader param names must match exactly** — `bt.Strategy` params are defined via `params = (...)`. Pass them with matching names in `cerebro.addstrategy()`.

8. **Web UI import path** — `app/main.py` needs a `sys.path` adjustment to import project root modules (config, data_manager, strategy). Add `sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))` before any local imports.

9. **QuantStats needs IPython** — `quantstats` imports `IPython.display` at module load time. Install `ipython` in the venv even if not running in a notebook.

## User Workflow Preferences (A-share investor)

- **Get it working first, optimize later** — prefer a working fallback (Tencent API) over debugging primary source (akshare)
- **Know the cost/complexity before committing** — present trade-offs (data source A vs B, CLI vs web) before building
- **Separate topics in responses** — when the user asks about multiple subjects, ask which to address first; do not mix answers in one response

## Extending the System

- **New indicator**: add class to `indicators.py`, instantiate in strategy `__init__`
- **New signal**: add condition in strategy `next()`
- **New sizer**: create `bt.Sizer` subclass, call `self.setsizer()`
- **New stop-loss**: add condition block in strategy `next()` under position check
- **Parameter optimization**: use `cerebro.optstrategy()` with param ranges
- **Multi-stock**: loop over stock codes, run separate Cerebro instances
