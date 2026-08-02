# mpquant/MyTT Evaluation

**Evaluated**: 2026-07-04 (concurrent with FinHackCN/finhack)
**Score**: N/A — Not a dependency decision; classified as "indicator reference library"
**Recommendation**: Use as formula reference only. Do not add as a runtime dependency.

## Why it was evaluated

User asked to compare FinHackCN/finhack vs mpquant/MyTT and give a comprehensive recommendation. Unlike FinHack (a full framework), MyTT is a ~100-line single-file library that converts TDX/THS (通达信/同花顺) formula indicators to pure numpy/pandas Python.

## Key findings

### What MyTT provides

- **Core primitives** (~20 functions): MA, EMA, SMA, CROSS, HHV, LLV, REF, SUM, COUNT, IF, MAX, MIN, ABS, STD, AVEDEV, SLOPE, FORCAST, EVER, EXIST, BARSLAST, LAST
- **Standard indicators** (~20): MACD, KDJ, RSI, BOLL, BIAS, CCI, ATR, WR, PSY, VR, OBV, MTM, ROC, DMI, TRIX, BRAR, MFI, EXPMA, BBI, TAQ, KTN
- Pure numpy/pandas, zero external deps (other than numpy/pandas)

### How it compares to the user's existing system

| Capability | MyTT | User's `_core.py` |
|------------|------|-------------------|
| TDX SMA | `SMA` | `TDX_SMA` |
| TDX EMA | `EMA` | `TDX_EMA` |
| TDX MA | `MA` | `TDX_MA` |
| TDX CROSS | `CROSS` | `TDX_CROSS` |
| TDX HHV | `HHV` | `TDX_HHV` |
| TDX LLV | `LLV` | `TDX_LLV` |
| TDX REF | `REF` | `TDX_REF` |
| TDX SUM | `SUM` | `TDX_SUM` |
| TDX IF | `IF` | `TDX_IF` |
| TDX COUNT | `COUNT` | `TDX_COUNT` |
| TDX MAX/MIN | `MAX`/`MIN` | `TDX_MAX`/`TDX_MIN` |
| TDX ABS | `ABS` | `TDX_ABS` |

**Result:** The user's `_core.py` has a 1:1 equivalent for every MyTT primitive. Many implementations are more rigorous (e.g., `TDX_REF` uses `np.roll` matching TDX semantics; `TDX_CROSS` explicitly handles NaN first-element edge case).

### What MyTT has that the user doesn't

Standard TDX indicators: MACD, KDJ, RSI, BOLL, BIAS, CCI, ATR, WR, PSY, VR, OBV, MTM, ROC, DMI, TRIX, BRAR, MFI, EXPMA, BBI, TAQ, KTN.

But these are each 3–10 lines built on the core primitives the user already has. The user's strategy doesn't use any of these — it uses custom-computed indicators (GS信号, 主力雷达, 暗盘资金, AI活跃度, 主力持仓) that are significantly more complex.

### What the user has that MyTT doesn't

- GS信号 — proprietary signal system based on EMA crossovers with bull/bear zone detection
- 主力雷达 — retail/institutional strength indicator
- 暗盘资金 — dark pool money flow estimation
- AI活跃度 — institutional activity scoring (0-10 scale)
- 主力持仓 — institutional holdings estimation
- Full backtesting pipeline (`backtest_v4.py`)
- IC/ICIR evaluation pipeline (`ic_analyzer.py`)
- Factor pre-calculation table (`daily_factors`)
- Tushare data pipeline
- SQLite factor DB

### Real use case for MyTT in this context

If the user ever needs to add a standard TDX indicator (say, DMI or MFI) to their factor table for IC testing:

1. Read MyTT's implementation (usually 3-10 lines of pandas/numpy)
2. Replicate using their own `_core.py` primitives
3. Register in `strategy_library/indicators/` as a new `_standard_tdx.py` module
4. Add to `daily_factors` factor list
5. Run `ic_analyzer.py` to evaluate

This is faster and cleaner than `pip install MyTT` — no import-time overhead, no version management, no dependency creep.

## Key files (from README)

- `MyTT.py` — entire library, single file
- `MyTT_plus.py` — advanced/experimental functions
- Available on PyPI as `pip install MyTT`

## Cross-reference

- See `finhack-evaluation-20260704.md` for the concurrent FinHack evaluation
- Both evaluated in the same session: "compare FinHackCN/finhack vs mpquant/MyTT, give comprehensive recommendation"
- Conclusion: neither should be introduced as a runtime dependency
