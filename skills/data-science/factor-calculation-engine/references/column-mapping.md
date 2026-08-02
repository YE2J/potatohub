# Column Mapping: Indicator Output → daily_factors DDL

## Indicator Output Column Names

Each `strategy_library.indicators` function returns a DataFrame with these columns:

### `calc_gs_signal(df)`
```
gs_bb, gs_a, gs_k, gs_p,
gs_g_point, gs_s_point,          # binary (0/1 via TDX_CROSS)
gs_zf, gs_zj, gs_jzf,           # continuous (%)
gs_tcy, gs_tzk,                  # binary (trend continuation)
gs_tkc, gs_tzd,                  # binary (breakdown)
gs_decision_line,                # EMA39 of JCx
gs_bull_line, gs_bear_line,      # based on mj20 vs mj30
gs_bull_market,                  # binary (mj20 >= mj30)
gs_support, gs_resistance,       # price levels
gs_ja, gs_jb                     # EMAs of a
```

### `calc_zhuli_radar(df)`
```
radar_maisell,                    # 0 or 30 (cross85 * 30)
radar_maibuy,                     # 0 or 30
radar_zhuli,                      # continuous [-100, 100]
radar_sanhu,                      # continuous [-100, 100]
radar_buy_signal,                 # binary (0/1)
radar_zhuli_cross,                # binary
radar_buy_signal2,                # binary
radar_sell_signal,                # binary
radar_rsi6, radar_ar, radar_varb, radar_varc  # aux
```

### `calc_ai_activity(df)`
```
ai_lifeline,                      # constant 1.56
ai_strong_line,                   # constant 3.0
ai_bull_line,                     # constant 6.0
ai_activity,                      # continuous [0, ~100]
ai_activity_breakout              # binary
```

### `calc_dark_pool(df, mf_df)`
```
dark_pool_1d,                     # continuous (元)
dark_pool_3d,                     # 3-day rolling sum
dark_pool_5d,                     # 5-day rolling sum
dark_pool_inflow_signal,          # boolean (暗盘资金 > 0)
dark_pool_accum_signal           # boolean (3d sum > 0)
```
Also merges in THS columns from moneyflow: `BIGBUYMONEY1`, `WAITBUYMONEY1`, etc.

### `calc_zhuli_holdings(df, mf_df)`
```
zhuli_holding,                    # continuous [2.08, 97.18]
zhuli_ddx_daily                  # continuous (%)
```

## Mapping to `daily_factors` DDL (FACTOR_FIELDS)

```python
FACTOR_FIELDS = [
    "gs_g_point", "gs_bull_market", "gs_tcy", "gs_tkc",
    "radar_zhuli", "radar_sanhu", "radar_maisell", "radar_buy",
    "ai_score", "ai_strong",
    "dark_pool_1d", "dark_pool_inflow_signal",
    "zhuli_holding", "zhuli_ddx_daily",
    "cross_zero",
]
```

| DDL field | Indicator | Indicator column | Conversion |
|-----------|-----------|-----------------|------------|
| gs_g_point | calc_gs_signal | `gs_g_point` | int(...) |
| gs_bull_market | calc_gs_signal | `gs_bull_market` | int(...) |
| gs_tcy | calc_gs_signal | `gs_tcy` | int(...) |
| gs_tkc | calc_gs_signal | `gs_tkc` | int(...) |
| radar_zhuli | calc_zhuli_radar | `radar_zhuli` | float(...) |
| radar_sanhu | calc_zhuli_radar | `radar_sanhu` | float(...) |
| radar_maisell | calc_zhuli_radar | `radar_maisell` | float(...) |
| radar_buy | calc_zhuli_radar | `radar_buy_signal` | **renamed**; int(...) |
| ai_score | calc_ai_activity | `ai_activity` | **renamed**; float(...) |
| ai_strong | calc_ai_activity | `ai_activity_breakout` | **renamed**; int(...) |
| dark_pool_1d | calc_dark_pool | `dark_pool_1d` | float(...) |
| dark_pool_inflow_signal | calc_dark_pool | `dark_pool_inflow_signal` | bool→int |
| zhuli_holding | calc_zhuli_holdings | `zhuli_holding` | float(...) |
| zhuli_ddx_daily | calc_zhuli_holdings | `zhuli_ddx_daily` | float(...) |
| cross_zero | N/A — computed | radar_zhuli[t-1]→[t] | 1 if prev<=0 and curr>0 else 0 |

## Moneyflow THS Column Mapping

`MoneyflowAdapter._map_to_ths_columns()` maps the DB schema to THS variable names:

| DB column | THS variable | Description |
|-----------|-------------|-------------|
| elg_buy_amt | BIGBUYMONEY1 | 特大单买入（元） |
| elg_buy_amt × 0.3 | WAITBUYMONEY1 | 特大单挂单 |
| lg_buy_amt | BIGBUYMONEY2 | 大单买入 |
| lg_buy_amt × 0.3 | WAITBUYMONEY2 | 大单挂单 |
| md_buy_amt | BIGBUYMONEY3 | 中单买入 |
| md_buy_amt × 0.3 | WAITBUYMONEY3 | 中单挂单 |
| elg_sell_amt | BIGSELLMONEY1 | 特大单卖出 |
| elg_sell_amt × 0.3 | WAITSELLMONEY1 | 特大单挂卖 |
| lg_sell_amt | BIGSELLMONEY2 | 大单卖出 |
| lg_sell_amt × 0.3 | WAITSELLMONEY2 | 大单挂卖 |
| md_sell_amt | BIGSELLMONEY3 | 中单卖出 |
| md_sell_amt × 0.3 | WAITSELLMONEY3 | 中单挂卖 |
| amount (from kline) | MONEY | 总成交额（需手动注入） |

**Important**: After mapping, the `MONEY` column must be injected from actual kline `amount` data, not from the moneyflow table's derived values. Pattern:

```python
mapped_mf = adapter._map_to_ths_columns(mf_df)
amt_map = dict(zip(kline_df["date"], kline_df["amount"]))
mapped_mf["MONEY"] = mapped_mf["date"].map(amt_map).fillna(0).values
```
