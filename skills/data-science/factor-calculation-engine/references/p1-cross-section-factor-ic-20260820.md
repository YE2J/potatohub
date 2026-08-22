# P1 Cross-Sectional Factor Pipeline — 2026-08-20 Session Learnings

Multi-factor IC evaluation built for ~/my_quant_system (A股). Reusable patterns and
verified data facts. Code: `factor_engine/cross_section_factors.py` +
`factor_engine/factor_ic_eval.py`; output table `factor_cross_section`
(7,887,310 rows / 1,608 trading days / 5,778 stocks / 2020-01-02~2026-08-20).

## Data pipeline pitfalls (all verified this session)

### 1. daily_kline has MIXED stock_code encoding — transitioned 2026-07-09
- Before 2026-07-09: mostly InnerCode (e.g. `605` = 华工科技, len<6)
- From 2026-07-09: uniformly 6-digit SecuCode (`000988`)
- Naive JOIN on stock_code silently misses ~60% of historical rows
  (observed: only 370 of 5,118 stocks got EP values before mapping added)
- Fix: map via `all_ashare_stocks.csv` (InnerCode→SecuCode), keep 6-digit as-is:
```python
inner_to_secu = dict(zip(m['InnerCode'].astype(str), m['SecuCode'].astype(str)))
df['secu'] = df['stock_code'].map(inner_to_secu)
df.loc[df['secu'].isna(), 'secu'] = df.loc[df['secu'].isna(), 'stock_code']
df = df[df['secu'].str.match(r'^\d{6}$', na=False)]
```

### 2. Dirty placeholder segment 2026-06-15 ~ 07-09
- Placeholder rows `close=10.0, volume=1000, amount=10000` market-wide (real
  close was 150-180). Filter:
```python
df = df[~((df['volume'] <= 1000) & (df['close'].abs() < 100))]
```

### 3. Price source: prefer daily_basic.close over daily_kline.close
- daily_basic (Tushare) is clean, full market from 2020, and carries
  pe_ttm/pb/total_mv/turnover_rate in the same row — no encoding issues.
- Verified daily_basic.close == daily_kline InnerCode rows exactly
  (e.g. 184.61 both sides for 000988 on 2026-06-30).
- Use daily_basic for price/return/valuation factors; use daily_kline only
  for `amount` (after mapping + dirty filtering).

### 4. scipy-free Spearman IC (pure pandas)
`.corr(method='spearman')` needs scipy. Equivalent without it:
```python
ic = g[factor].rank().corr(g['fwd_ret'].rank())  # Pearson on ranks == Spearman
```

## Factor evaluation methodology

- Daily cross-sectional Spearman IC, then mean/std → ICIR; win rate = P(IC>0).
- 5-group quantile backtest is mandatory, not optional:
  **IC≈0 but perfect quantile monotonicity = nonlinear factor** — use it as a
  screen/quantile signal, NOT a linear weight. (NF_5D case below.)
- Market-cap neutralization: OLS residual of factor on ln(total_mv)
  (np.linalg.lstsq), then recompute IC on residuals.
- Judgment thresholds used: IC_mean ≥0.03 pass | ≥0.02 weak | <0.02淘汰,
  plus quantile monotonicity check; negative-IC factors judged after sign flip.

## Empirical A-share results (near-250-day window, 2025-08~2026-08)

| Factor | IC_1d | IC_5d | Quantile monotonic (5d) | Verdict |
|--------|-------|-------|-------------------------|---------|
| NF_5D 资金流强度 | ~0 | +0.010 | **4/4 perfect** (Q1=-0.11%→Q5=+0.38%) | strong, nonlinear |
| Rev_20 20日反转 | +0.036 | +0.048 | 3/4 | pass |
| Turn_20 换手率 | -0.045 | -0.059 | low-group wins | pass after flip |
| Mom_60_20 动量 | -0.015 | -0.029 | Q1 wins | weak (A股反转) |
| BP 账面市值比 | +0.027 | +0.035 | 2/4 | weak |
| Vol_20 波动率 | -0.050 | -0.060 | 1/4 | IC strong, unstable |
| EP_TTM | +0.019 | +0.024 | U-shape | eliminated |

Key insights:
- A股反转 > 动量 (consistent with Liu-Stambaugh-Yuan 2019 QJE)
- Low turnover / low volatility premium (negative IC, flip for long)
- Valuation factors weak — EP_TTM eliminated; possibly pe_ttm coverage gap
  (loss-making stocks lack pe_ttm)
- Market-cap neutralization barely changes IC → effects not pure small-cap

## Tools
- `factor_engine/cross_section_factors.py` — market-wide factor calc,
  INSERT OR REPLACE batching (2000 rows/batch), idempotent re-runs.
- `factor_engine/factor_ic_eval.py` — IC/ICIR/win rate/quantile/neutralization
  + Chart.js HTML report at `reports/factor_ic_report.html`.
- Full session report: `docs/P1_factor_ic_report.md`.
