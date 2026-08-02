# Factor Engine Design Document

Full technical design: `~/my_quant_system/docs/factor_engine_design.md`

## Key Data Points (verified against production DB)

| Dataset | Rows | Memory | Notes |
|---------|------|--------|-------|
| daily_kline (120d) | 649,409 | 114.6 MB | 9 cols, 10,910 stocks |
| moneyflow THS (60d) | 207,490 | 38.4 MB | 10 cols, 5,210 stocks |
| Intersection | 5,193 stocks | ~155 MB total | Steady-state |
| pd.read_sql peak | — | ~350 MB | Temporary during loading |

## SQL Schema

- `daily_kline`: `(stock_code, date, open, high, low, close, volume, amount, pct_change, ...)` — PK: `(stock_code, date)`
- `moneyflow_daily`: `(stock_code, date, elg_buy_amt, elg_sell_amt, lg_buy_amt, lg_sell_amt, md_buy_amt, md_sell_amt, sm_buy_amt, sm_sell_amt, data_source, ...)` — PK: `(stock_code, date)`

## Date Format Quirk

daily_kline has TWO date formats:
- `"20260105"` — no hyphens, used for ~142 watchlist stocks (before 2026-06)
- `"2026-06-15"` — ISO with hyphens, used for full market (~5,200 stocks)
- Use `normalize_date_format()` in Python after loading

## Performance Records

Tested against stock_data.db (3.9 GB):
- Batch load + groupby: ~5 seconds
- Per-stock calc (serial): ~1.5 minutes
- Per-stock calc (4 workers): ~25 seconds
- Batch DB write (500/batch): ~2 seconds
