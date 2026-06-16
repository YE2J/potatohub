---
name: a-share-backtest-platform
description: "Build and run A-share quantitative backtesting systems using Backtrader, with local data storage (SQLite+Parquet), custom strategies, and a FastAPI web UI for interactive use."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [backtrader, backtest, a-share, quantitative, fastapi, web-ui, strategy-editor]
    related_skills: [valuation-channel, minute-level-data-analysis, tushare-data]
---

# A-Share Backtest Platform

A complete local quantitative backtesting platform for A-shares, built with Backtrader, FastAPI, and the Tencent stock API.

## Architecture

```
Tencent API ──→ data_manager.py ──→ SQLite + Parquet
                                        ↓
Backtrader engine ← strategy.py / custom strategies
      ↓
FastAPI Web UI (watchlist, config, results, reports)
      ↓
QuantStats HTML report + SQLite results table
```

## Key Components

### 1. Data Acquisition (`data_manager.py`)

- **StockDataManager** class with dual-source fallback:
  1. `akshare` (EastMoney) — may fail from non-Chinese IP
  2. Tencent API (`web.ifzq.gtimg.cn`) — reliable fallback
- Stores data in **SQLite** (`daily_kline` table) and **Parquet** for fast reads
- **CRITICAL PITFALL**: The Tencent API's kline entries have an optional 7th field that's a **dict** (dividend/ex-right info), not a float. Always take only the first 6 fields: `[date, open, close, high, low, volume]`.

### 2. Tencent API Details

Endpoint: `https://web.ifzq.gtimg.cn/appstock/app/fqkline/get`
Query param: `param={sz|sh}{code},day,{start},{end},{count},qfq`
- **sz** prefix for Shenzhen stocks (0/3/001xxx codes)
- **sh** prefix for Shanghai stocks (6/5/688xxx codes)
- Returns up to **500** records per request (capped)
- Response structure: `data[sec_id].qfqday` (adjusted) or `.day` (unadjusted)
- Rate limit: ~8 requests/second safe, 0.12s delay between calls

### 3. Strategy System (`strategy.py`)

Built-in `MyStrategy` (SMA crossover) + **custom strategy support**:

**Custom strategies** are Python files stored in `web_data/strategies/{name}.py`:
```python
import backtrader as bt
from indicators import SMA, EMA, ATR

class CustomStrategy(bt.Strategy):
    params = (('stop_loss', 0.05), ('trailing_stop', 0.03), ('time_stop', 10))

    def __init__(self):
        # Define indicators here
        self.sma5 = SMA(self.data.close, period=5)
        self.crossover = bt.indicators.CrossOver(...)
        # State variables (required)
        self.order = None; self.buy_price = None
        self.high_since_entry = None; self.buy_date = None

    def next(self):
        # Buy/sell logic here
        pass
```

**CRITICAL PITFALL — Dynamic strategy loading**: When using `importlib` to load custom strategy files, you MUST register the module in `sys.modules` BEFORE executing it, or Backtrader's metaclass will raise `KeyError`:
```python
module = importlib.util.module_from_spec(spec)
sys.modules[module_name] = module  # ← REQUIRED
spec.loader.exec_module(module)
```

### 4. Web UI (`app/main.py`)

FastAPI app with Jinja2 templates (Bootstrap 5 dark theme):
| Route | Function |
|-------|----------|
| `/` | Dashboard (stats, latest backtest) |
| `/watchlist` | Watchlist management |
| `/strategies` | Strategy CRUD |
| `/strategies/edit` | Code editor |
| `/backtest` | Run backtests with param config |
| `/history` | View past results |

### 5. Backtest Result Storage

SQLite `backtest_results` table stores: stock_code, date range, initial/final value, total/annual return, Sharpe ratio, max drawdown, win rate, profit/loss ratio, total/winning/losing trades, timestamp.

## Pitfalls

1. **akshare (EastMoney) from non-China IP**: The API at `push2his.eastmoney.com` often returns `RemoteDisconnected` errors. The Tencent API is a reliable fallback accessible from anywhere.
2. **Tencent API kline 7th field**: Some entries have a dividend-info dict as the 7th element. Parse only indices [0..5].
3. **Backtrader dynamic module loading**: Must register in `sys.modules` before execution.
4. **FastAPI `request.args` vs `request.query_params`**: Starlette uses `request.query_params.get('key')`, NOT `request.args.get('key')` (Flask convention).
5. **Uvicorn background processes**: The `reload=True` mode may cause unexpected restarts. Use stable mode (`reload=False`) for long-running servers.
6. **Long background operations**: Hermes background processes (≥30s) may be killed. Use foreground with sufficient timeout, nohup, or cronjobs for long downloads.
