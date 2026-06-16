# 估值子进程隔离方案

When integrating `valuation_channel` into a web application (FastAPI/uvicorn),
the matplotlib + akshare stack can cause the web server process to hang.
The proven workaround is to run the valuation in a standalone subprocess.

## Why

- `matplotlib.use('Agg')` conflicts with uvicorn's async event loop
- `from valuation_channel import ValuationAssessor, ...` importing multiple names at once
  can trigger the hang, while importing them sequentially does not (inconsistent)
- `DataFetcher.get_kline()` pagination loop may deadlock in certain Python environments

## Pattern

```python
import subprocess, json, sys

codes = ["000001", "600519"]
result = subprocess.run(
    [sys.executable, "run_valuation_subprocess.py", json.dumps(codes)],
    capture_output=True, text=True, timeout=300
)

# Parse structured JSON from output
marker = "---RESULT_JSON---"
if marker in result.stdout:
    json_str = result.stdout.split(marker)[1].split("---END---")[0].strip()
    data = json.loads(json_str)
```

## Standalone Script Template

The subprocess script should:
1. Set `matplotlib.use('Agg')` at the top, before any other imports
2. Import `valuation_channel` classes (sequence doesn't matter in a subprocess — no uvicorn)
3. For each stock code:
   - Call `DataFetcher.get_stock_name(code)`
   - Option A: use `ValuationAssessor.evaluate(code)` for full multi-model report
   - Option B: compute PE channel directly from SQLite K-line data (simpler, faster)
4. Save chart to `reports/valuation/{code}.png`
5. Write results to SQLite `valuation_results` table
6. Print JSON results between `---RESULT_JSON---` and `---END---` markers

## Simplified Alternative

For web integration, you can skip the full `valuation_channel.py` dependency
and implement a lighter version that:
- Reads K-line from SQLite (via `data_manager.StockDataManager` or direct SQL)
- Fetches EPS via `akshare.stock_financial_abstract_ths()`
- Computes TTM PE and channel bands (same algorithm, ~60 lines)
- Generates chart with matplotlib (no mplcursors needed for server-side)
- Saves to DB

This avoids the hanging issue entirely and runs in ~15s per stock.

See `run_valuation_subprocess.py` in the my_quant_system project for a
complete working implementation.
