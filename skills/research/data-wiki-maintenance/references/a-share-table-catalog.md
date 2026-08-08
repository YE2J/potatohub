# A-Share Database Table Catalog (stock_data.db)

Reference for the A-share data pipeline tables tracked by the wiki.
Discovered during the 2026-07-12 valuation correction session; extended
2026-08-05 (index ts_code mapping, concept/industry semantics, leader_stocks);
2026-08-07 (sector_moneyflow_dc/market_moneyflow/limit_up_pool columns,
factor_run_log, two new job IDs, rowid quirk).

## K线 (Price)

| Table | Date Column | Date Format | Notes |
|-------|-------------|-------------|-------|
| `daily_kline` | `date` | `YYYY-MM-DD` | Primary. also has legacy YYYYMMDD rows (~147, watchlist only). Columns: stock_code, date, open, high, low, close, volume, amount, amplitude, pct_change, change, turnover. **NOT `trade_date`**, **NO `stock_name`** — join `stock_name_map` for names. |
| `daily_factors` | `trade_date` | `YYYY-MM-DD` | Factor data on same stocks. |

## 资金流 (Fund Flow)

| Table | Date Column | Date Format | Notes |
|-------|-------------|-------------|-------|
| `moneyflow_daily` | `date` | `YYYY-MM-DD` | Primary. `net_mf_amt` = net flow (单位 元, 亿元 = /1e8). `data_source='tushare_dc'` for DC rows. 全市场净额 = `SUM(net_mf_amt)/1e8`, cross-check vs `market_moneyflow.main_net_inflow` (实测 08-06: -382.7 vs -382.56 亿). |
| `sector_moneyflow_dc` | `trade_date` | **`YYYYMMDD`** ⚠️ | **= 概念板块** — the morning report (v7) reads THIS table for 概念 TOP5. 实测列 (2026-08-07 PRAGMA): trade_date, sector_code, sector_name, pct_change, close_price, net_amount (元, 亿元=/1e8), net_amount_rate, buy_elg_amount, buy_lg_amount, buy_md_amount, buy_sm_amount, buy_elg_rate, buy_lg_rate, buy_md_rate, buy_sm_rate, rank. **NO `inflow_days`** (that's `sector_rotation`); querying a missing column returns EMPTY silently. |
| `industry_moneyflow_dc` | `trade_date` | `YYYYMMDD` | **= 行业板块** — morning report (v7) reads THIS table for 行业 TOP5 (`industry_code/industry_name/net_amount/pct_change`). Do NOT use sector_moneyflow_dc for industries. |
| `hsgt_moneyflow` | `trade_date` | `YYYYMMDD` | 北向/南向. |
| `industry_moneyflow_ths` | `trade_date` | `YYYYMMDD` | THS industry level. |
| `sector_moneyflow_ths` | `trade_date` | `YYYYMMDD` | THS sector level. |
| `market_moneyflow` | `trade_date` | `YYYYMMDD` | 大盘资金流 — 1 row/day. 实测列 (2026-08-07): trade_date, sh_close, sh_pct_change, sz_close, sz_pct_change, main_net_inflow (元, 亿元=/1e8), main_net_inflow_ratio, elg/lg/md/sm_net_inflow + ratios. **Pipeline ACTIVE** — has 08-04/05/06 rows; the old "大盘资金流 script missing (07-16起)" wiki claim was STALE (corrected 08-07). |

## 估值 (Valuation) — ⚠️ CRITICAL: Two tables

| Table | Date Column | Date Format | Status | Notes |
|-------|-------------|-------------|--------|-------|
| `valuation_results` | `run_id` (int) / `run_date` | `YYYY-MM-DD HH:MM:SS` | ✅ ACTIVE | v3.2 PE-Band model. Use `MAX(run_id)`, NOT `MAX(run_date)`. |
| `valuation_daily_signal` | `trade_date` | `TEXT` | ❌ EMPTY | v1 old model. **Do not track this table.** |

**valuation_results key columns:**
- `run_id` (INTEGER) — batch identifier, use `MAX(run_id)` for latest
- `data_as_of` (DATE) — data cutoff date (for staleness tracking)
- `run_date` (DATETIME) — when batch ran
- `safety_margin` (REAL) — decimal, ×100 for %. Positive=undervalued
- `rating` (TEXT) — 显著低估/低估/偏低/中性/偏高/高估/显著高估
- `primary_model` / `model_version` — model tracking

## 指数 (Index)

| Table | Date Column | Date Format | Notes |
|-------|-------------|-------------|-------|
| `index_daily` | `trade_date` | `YYYY-MM-DD` | Major indexes. Column is **`ts_code`** (NOT index_code) + `pct_chg` (NOT pct_change). Code mapping: `000001.SH`=上证指数, `399001.SZ`=深证成指, `399006.SZ`=创业板指, `000688.SH`=科创50, `000300.SH`=沪深300. **Never ORDER BY rowid DESC** — returned 2024-01 rows as "latest" (rowid unreliable after bulk reload). Use `WHERE trade_date = (SELECT MAX(trade_date) FROM index_daily)` or `SELECT ts_code, MAX(trade_date) ... GROUP BY ts_code`. |

## 涨停异动 (Limit-up / Anomalies)

| Table | Date Column | Date Format | Notes |
|-------|-------------|-------------|-------|
| `dragon_tiger_daily` | `trade_date` | `YYYY-MM-DD` | 龙虎榜 (08-04: 85 条) |
| `daily_anomaly` | `trade_date` | `YYYY-MM-DD` | 个股异动 |
| `hot_stock_daily` | `trade_date` | `YYYY-MM-DD` | 市场热榜. 列: thscode, stock_name, rank, rank_type, score, pct_chg, current_price (实测 2026-08-04). Query `WHERE rank_type='day' ORDER BY rank`. Also usable as NAME FALLBACK for codes missing from stock_name_map (实测 001232=嘉立创, 688825=长鑫科技). |
| `limit_up_pool` | `trade_date` | `YYYY-MM-DD` | 涨停池 (08-03: 75 只, 08-04: 137 只, 08-05: 102, 08-06: 39). 列 (实测 2026-08-07): trade_date, thscode, stock_name, first_limit_time, last_limit_time, open_times, limit_reason, board_count, turnover_rate, close_price, pct_chg, amount, fd_amount, market_cap. **涨停数骤降 (102→39) = 情绪降温信号** — report trend vs 前一日. |
| `limit_up_ladder` | `trade_date` | `YYYY-MM-DD` | 连板天梯 (08-03: 6 条, 08-04: 6 条) |
| `leader_stocks` | `trade_date` | `YYYY-MM-DD` | L2 龙头引擎输出. Columns: stock_code, stock_name, sector_code, sector_name, leader_score, leader_type (涨停龙头/资金/趋势), board_count, main_net_amount, channel_position, pe_ttm, safety_margin. **No `rank` column** — rows are the leaders themselves (usually 1-3 per day, 08-05: 7 只). |

## 辅助表 (Helper)

| Table | Columns | Purpose |
|-------|---------|---------|
| `stock_name_map` | stock_code (PK), stock_name, source | Name lookup for any stock code. Simpler than daily_kline join (which has NO name column). Missing codes → fall back to hot_stock_daily; if still missing keep "(新股)" descriptor (e.g. 688825). |
| `cron_push_log` | id, job_name, job_id, status, finished_time, content_path, duration_ms, log_tail | Cron execution history. Query `ORDER BY id DESC` for latest. |
| `factor_run_log` | run_id, run_type, target_date, stock_count, success_count, fail_count, version, started_at, finished_at, duration_sec, error_message | 因子更新汇总. **Health = `fail_count`** (0 = ok even when the cron log shows per-stock `[ERR] dark_pool/zhuli_holdings: operands could not be broadcast` noise — 688xxx/605xxx stocks, observed 08-04~08-06). |
| `market_temperature` | trade_date, temperature_score, market_label, position_ratio, index_trend_score, capital_flow_score, sentiment_score, sh_index_close, sh_ma20, sh_ma60, north_net_amount, up_down_ratio, limit_up_count, limit_down_count, total_amount, trend_direction, consistency_score | 大盘温度 (0-100). 实测完整列 (2026-08-04 PRAGMA): `trend_direction` 存在 (值 up/down/stable), `limit_up_count`/`limit_down_count` 存在, `up_down_ratio` (涨跌比), `total_amount` (成交额), `market_label` = 冰点/低温/常温/高温. **NOT `temperature`/`position`/`trend`** — use `temperature_score`/`position_ratio`/`trend_direction`. |
| `margin_balance` | trade_date (`YYYYMMDD`), exchange_id (SSE/SZSE/BSE), rzye, rzmre, rzche, rqye, rqmcl, rzrqye | 两融余额. 每日期 **3 行**（每交易所一行）. `rzrqye` = 两融余额, 单位 **元** (亿元 = /1e8). 全市场 = SUM(rzrqye). |
| `sector_rotation` | trade_date, sector_code, sector_name, sector_type (concept/industry), heat_score, rank, net_amount, inflow_days, cumulative_net, leader_stock, leader_name, stage, consecutive_top5, data_version | L2 板块轮动引擎输出. `sector_type` distinguishes concept vs industry. |
| `decision_log` | trade_date, decision_type (buy/sell/hold/cash/watch), stock_code, stock_name, confidence, position_ratio, l1_temperature, sector_name | L1+L2 决策融合输出. `watch` rows carry stock_code/stock_name. |

## Verification Query Template (Updated)

```sql
-- Quick health check for all tracked tables
SELECT 'daily_kline' as tbl, MAX(date) as latest, COUNT(*) as cnt FROM daily_kline
UNION ALL
SELECT 'daily_factors', MAX(trade_date), COUNT(*) FROM daily_factors
UNION ALL
SELECT 'moneyflow_daily', MAX(date), COUNT(*) FROM moneyflow_daily
UNION ALL
SELECT 'margin_balance', MAX(trade_date), COUNT(*) FROM margin_balance
UNION ALL
SELECT 'valuation_results', MAX(data_as_of), COUNT(*) FROM valuation_results
UNION ALL
SELECT 'index_daily', MAX(trade_date), COUNT(*) FROM index_daily
UNION ALL
SELECT 'dragon_tiger_daily', MAX(trade_date), COUNT(*) FROM dragon_tiger_daily
UNION ALL
SELECT 'stock_name_map', null, COUNT(*) FROM stock_name_map
ORDER BY tbl;
```

```sql
-- 全市场净额双源交叉验证 (should agree, e.g. 08-06: -382.7 / -382.56 亿)
SELECT date, ROUND(SUM(net_mf_amt)/1e8,1) FROM moneyflow_daily
WHERE date IN ('2026-08-04','2026-08-05','2026-08-06') GROUP BY date;
SELECT trade_date, main_net_inflow/1e8 FROM market_moneyflow ORDER BY trade_date DESC LIMIT 3;
```

## Pipeline Job-ID → Purpose Map (cron output dirs)

`~/.hermes/cron/output/<job_id>/` holds one `.md` per run. IDs verified 2026-08-05
and 2026-08-07; they are stable but re-verify if a job stops producing output.

| Job ID | Schedule | Purpose |
|--------|----------|---------|
| `0c029d10767b` | 18:00 | 前复权日线-Tushare增量 (daily_kline, 5200+ 只/日) |
| `910124571b2d` | 18:30 | 资金流向-Tushare-DC增量 (moneyflow_daily) |
| `9f318247dfd0` | 18:30 | 大盘资金流-每日增量 (market_moneyflow + hsgt_moneyflow, 1 row/day each) |
| `7bfe1d8efccc` | 18:35 | 两融余额 (margin_balance) |
| `9139d87aa0e2` | 18:45 | 板块资金流 THS |
| `636c702ec9f1` | 18:50 | 板块资金流 DC (sector/industry_moneyflow_dc, T-1) |
| `e5e967ea3aeb` | 19:00 | L1 大盘温度 (market_temperature) |
| `263ec7d6d324` | 19:02 | 每日因子更新 (daily_factors) |
| `cddbd144447` | 20:00 | 因子回填-持续 (backfill) |
| `62f94e3b9c5a` | 20:00 | L2 板块轮动 (sector_rotation) |
| `2b2fdbdd0953` | 20:30 | L3 决策融合 (decision_log) |
| `395cb3e7080b` | 22:00 | 市场热榜 (hot_stock_daily) |
| `baab58cec144` | 00:00 | DNS 缓存更新 |
| `dd25f44abecd` | 07:00 | 内置盘容量监控 (often silent) |
| `3cb6fbcc8dcc` | 07:05 | 每日晨报 (daily morning report) |
| `82d135d6a369` | 03:35 | **本 Wiki 增量任务自身** (previous run's full report = best context for what was last reported) |

## Historical Correction

- Prior to 2026-07-12, the wiki tracked `valuation_daily_signal` (empty) and
  reported "valuation stagnant 24 days." Actual data was in `valuation_results`
  with latest run 2026-07-11.
- 6 consecutive wiki updates (07-05 through 07-11) compounded this error.
- All affected pages were corrected on 2026-07-12 with timestamped corrections.
- 2026-08-07: corrected 3 stale claims — ① DC sector moneyflow / L2 rotation /
  L3 decision HAD advanced to 08-05 (previous entry said "维持 08-03" — the
  sector script's "已是最新 跳过" from 08-05 evening did NOT recur on 08-06
  evening, it fetched 08-05 data); ② 两融 08-04 "疑似漏采" was backfilled to
  26,152.21 亿 on 08-06 evening (self-heal, don't carry the flag forward);
  ③ 大盘资金流 "script missing (07-16起)" was STALE — market_moneyflow had
  continuous rows 08-04/05/06. Lesson: re-verify every persistent 🔴/🟡 flag
  against the actual table; negative claims harden like positive ones.
