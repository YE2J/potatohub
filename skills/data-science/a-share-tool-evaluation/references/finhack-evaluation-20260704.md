# FinHackCN/finhack Evaluation

**Evaluated**: 2026-07-04
**Score**: 2/10 — Not Recommended

## Why it was evaluated

User asked whether FinHackCN/finhack suits their "factor mining" needs — specifically reverse-mining: "given buy/sell signals (买卖点), find which factors most contribute to those signals."

## Key findings

### What finhack actually does for "factor mining"

Two paths:

1. **LLM-driven** (`factorMining.openai()`/`gpt()`/`kimi()`): Calls OpenAI/Kimi API to generate Alpha101-style formula strings → parses them with alphaEngine → calculates → evaluates with Alphalens. Pure random generation, no directed search.

2. **GP-driven** (`factorMining.gplearn()`): Uses `gplearn.SymbolicTransformer` for genetic programming symbolic regression. Custom function set includes correlation, covariance, ts_sum, ts_rank, delta, delay, stddev, etc. Produces mathematical expressions like `Rank(Corr(Close, Volume, 5))`.

**Neither addresses the user's actual need**: "given a specific buy/sell signal, find which features most contributed to it." That's a supervised attribution/feature-importance problem (LightGBM + SHAP), not an unsupervised alpha-generation problem.

### Fatal issues

| Issue | Severity | Detail |
|-------|----------|--------|
| **Code Doesn't Run** | 🔴 | README says "今天开始更新的代码，运行不了了！" Version 0.0.3.dev2. Requires runtime-generated `constant.py` that doesn't exist in repo. |
| **No SQLite Support** | 🔴 | `mydb.py` only supports MySQL and DuckDB. User's 2.2GB SQLite stock_data.db is completely incompatible. |
| **Heavy Dependencies** | 🟡 | 73+ packages including dask, flask, redis, lightgbm, alphalens-reloaded, ta-lib. User's stack is pure pandas/numpy. |
| **Project Architecture** | 🟡 | Requires `finhack project create` + CLI-initiated project structure + configparser .conf configuration. Not drop-in compatible. |
| **GPL-3.0** | 🟡 | Commercial use requires paid license from author. |

### What the user actually needs

A lightweight extension to their existing `~/my_quant_system`:

1. **Signal attribution** (ic_analyzer.py extension): For each buy/sell signal, compute factor changes N-days before trigger → find discrimination power via simple logistic regression or LightGBM + SHAP.

2. **Supervised factor search** (alternative to gplearn): Define a custom gplearn objective that maximizes signal-trigger discrimination rather than predicting returns. Requires only `pip install gplearn` — no 70+ deps.

### Modules read

| File | Lines | Notes |
|------|-------|-------|
| `finhack/factor/default/factorMining.py` | 366 | Core: LLM + GP mining. Uses gplearn 0.4.2 + openai API. |
| `finhack/factor/default/alphaEngine.py` | 951 | Formula parser. AST-based ternary transform. |
| `finhack/factor/default/factorAnalyzer.py` | 455 | Alphalens wrapper. IC, quantile, autocorrelation. |
| `finhack/trader/default/default_trader.py` | 288 | Event-driven backtest engine, multiprocess. |
| `finhack/library/mydb.py` | 499 | MySQL/DuckDB abstraction. No SQLite. |
| `finhack/core/core.py` | 243 | CLI project lifecycle. Dynamic runtime generation. |
| `finhack/trainer/lightgbm/lightgbm_trainer.py` | 344 | LightGBM with correlated feature filtering. |
| `requirements.txt` | 304 | 73+ packages. |

### User's existing system (for comparison)

- Database: SQLite, `~/my_quant_system/stock_data.db`
- Factor pipeline: `factor_engine/factor_pipeline.py` + `strategy_library/factors.py`
- IC evaluation: `strategy_library/evaluation/ic_analyzer.py` (628 lines, pure pandas)
- Backtest: `backtest_v4.py` (~685 lines, pure pandas)
- Python: 3.11.11
- Data: Tushare + moneyflow DC pipeline
- Preference: lightweight, few deps, readable, SQLite-native

## Cross-reference

- See `mytt-evaluation-20260704.md` for the concurrent MyTT evaluation
- Both evaluated in the same session: "compare FinHackCN/finhack vs mpquant/MyTT, give comprehensive recommendation"
- Conclusion: neither should be introduced as a runtime dependency
