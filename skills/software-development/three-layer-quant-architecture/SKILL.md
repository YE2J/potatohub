---
name: three-layer-quant-architecture
description: Build A-share quant system in layers with review gates.
version: 0.2.0
author: Hermes
metadata:
  hermes:
    tags: [A-share, Quantitative, Architecture, MultiAgent]
---

# Three-Layer Quant Architecture Build

Build an A-share quantitative decision system as three decoupled engines
(L1 market temperature → L2 sector rotation → L3 valuation gate + fusion),
each validated by a 4-agent Kanban review before moving to the next layer.

Does NOT cover: individual factor research, backtesting infrastructure,
or trade execution. It is the *build sequence and quality gate* workflow.

## When to Use

- Starting a new A-share quant system from scratch.
- Reviewing where the current system is in the layer progression.
- Planning the next engine after finishing a previous layer.
- Debugging why a newly built engine produces wrong signals (check the
  common-bug checklist in Pitfalls).

## Prerequisites

- Hermes Kanban profiles: `worker-glm`, `worker-kimi`, `worker-auditor`,
  `orchestrator` (each with its own LLM model config).
- Gateway running with `dispatch_interval_seconds: 15` (config.yaml).
- Tushare pro API 5000+ credits; env var or config.
- `scripts/db_utils.py` with `get_conn()` (PRAGMA-optimized connections).
- `scripts/kanban_await.py` for auto-push of Kanban results.
- `scripts/valuation_utils.py` — shared module with `get_ts_code()`, `calc_channel_position()`,
  `rating_from_position()`, `compute_safety_margin()` (used by both refresh scripts).

## How to Run

The canonical build order: P1 data facilities → P2 L1 → P3 L2 → P4 L3.
Each phase: implement → 4-agent Kanban review → fix P0s → re-verify.

Engine files go in `engines/`, cron scripts in `scripts/`, docs in `docs/`.
Output tables are pre-created via migration SQL.

## Quick Reference

| Phase | Engine file | Cron | Output table |
|:------|:-----------|:-----|:-------------|
| P1 | migrations/*.sql, scripts/*.py | — | ths_member, sector/industry moneyflow |
| P2 L1 | engines/market_temperature.py | 19:00 | market_temperature |
| P3 L2 | engines/sector_rotation.py | 20:00 | sector_rotation, leader_stocks |
| P4 L3 | engines/decision_fusion.py | 20:30 | decision_log + valuation_results |

| Review cycle per phase: 4 Kanban worker cards → orchestrator synthesis → fix P0s.

## Data Pipeline Timeline (Cron Schedule)

The complete daily cron pipeline drives all three layers. Order matters — each layer
depends on data from the previous step:

```
18:00  daily_basic + 前复权日线 + 指数日线  (已有: pro.daily(adj=qfq) + index_daily)
18:30  大盘资金流 + 北向资金                (daily_market_moneyflow.py, moneyflow_mkt_dc + moneyflow_hsgt)
18:45  板块资金流                           (daily_sector_moneyflow.py, moneyflow_cnt_ths + moneyflow_ind_ths, no_agent)
─────────────────────────────────────
19:00  L1 大盘温度                          (market_temperature.py, cron:engine)
20:00  L2 板块轮动                          (sector_rotation.py, cron:engine)
20:30  L3 决策融合                          (decision_fusion.py, cron:engine)
```

Each cron runs only on A-share trading days (checked via `trade_cal`).
L1/L2/L3 engine crons are Hermes agent-driven crons (no_agent=false, full LLM).
Data-collection crons are no_agent=true (script-only, zero token cost).

### Cron registration examples

```bash
# L1 (agent-driven)
hermes cron create "大盘温度-每日计算" --schedule "0 19 * * 1-5" \
  --prompt "运行 engines/market_temperature.py"

# 板块资金流 (no_agent, pure script)
hermes cron create "板块资金流向-每日增量" --schedule "45 18 * * 1-5" \
  --script scripts/daily_sector_moneyflow.py --no_agent
```

### Phase 0: Data Infrastructure

1. Ensure every target table exists (create if not, via `migrations/`).
2. Collect `ths_member` (sector-to-stock mapping): `pro.ths_member()` per
   sector code. Skip index/ST/次新股 sectors.
3. Backfill `sector_moneyflow_ths` and `industry_moneyflow_ths` at least
   60 trading days: `pro.moneyflow_cnt_ths()` / `pro.moneyflow_ind_ths()`.
4. Register no-agent crons for daily incremental collection at `18:30-18:45`.
5. Verify: each table has data, JOIN keys are consistent (strip `.SZ/.SH/.TI`
   suffixes as needed).

### Phase 1: L1 Market Temperature Engine

Build `engines/market_temperature.py` with three dimension methods:
- `calc_index_trend(date)` → 5-index weighted MA arrangement + MACD
- `calc_capital_flow(date)` → capital + north-bound + margin (dynamic weight)
- `calc_sentiment(date)` → advance-decline ratio + limit-up/down + volume

Temperature→position map: no cliff jumps (e.g. T=80→60% not T=80→20%).
Use `pandas.ewm(adjust=False)` for MACD (not SQL SMA).
Register cron at 19:00 (after fund-flow data arrives at 18:30-18:45).

### Phase 2: L2 Sector Rotation Engine

Build `engines/sector_rotation.py`:
- Read `sector_moneyflow_ths` + `industry_moneyflow_ths` for fund flow.
- Calculate consecutive inflow days, cumulative net, fund slope.
- Join `ths_member` to calculate MA20-above ratio per sector.
- Composite heat score: inflow(30%) + slope(15%) + index-change(15%) +
  MA-ratio(25%) + leader-strength(15%).
- Identify leader stocks: limit-up leader (earliest seal time) + fund leader.
- Register cron at 20:00.

### Phase 3: L3 Valuation Gate + Decision Fusion

Build `engines/decision_fusion.py`:
- Read L1 `market_temperature` for position cap.
- Read L2 `sector_rotation` + `leader_stocks` for candidates.
- Gate each candidate through `valuation_results.channel_position`:
  - `pos <= 35` → buy (if safety_margin >= -20%)
  - `pos >= 85` → sell
  - `None` → hold (conservative).
- Fusion: sort by score (buy candidates +30, sell -50), cap count per position.
- Register cron at 20:30.

### Post-L3: Leader Stock Valuation Extension

After L3 is built, the system has `valuation_results` covering ~110 self-selected
stocks, but L2 leader stocks may not be covered. To extend:

1. Find missing leaders:
```sql
SELECT l.stock_code, l.stock_name, l.sector_name, l.leader_score
FROM leader_stocks l
LEFT JOIN valuation_results v ON l.stock_code = v.stock_code
WHERE l.trade_date = (SELECT MAX(trade_date) FROM leader_stocks)
  AND v.stock_code IS NULL
ORDER BY l.leader_score DESC;
```

2. Run dedicated refresh script with leader stock codes:
```bash
cd ~/my_quant_system && ~/.pyenv/versions/3.11.11/bin/python3 \\
    scripts/refresh_leader_valuation.py
```

3. Re-run decision fusion; new buy signals may appear for leader stocks
   with channel_position ≤ 35%.

**⚠️ Date format trap (fixed in v3.3):** `leader_stocks.trade_date` stores dates
as `YYYY-MM-DD` (e.g. `2026-07-08`) while `daily_kline.date` and `daily_basic`
API calls use `YYYYMMDD` format. The original script hardcoded `20260710` and
queried `leader_stocks WHERE trade_date=?` — which never matched, returning
empty results silently. The fix:

```python
# Keep YYYY-MM-DD for DB queries against leader_stocks
trade_date = raw_date  # '2026-07-08' format
query_date = raw_date.replace('-', '')  # '20260708' for Tushare API
```

The `refresh_leader_valuation.py` v3.3+ handles both formats automatically
via `--date` (accepts either `20260710` or `2026-07-10`).

### Auto-Push Pattern (Kanban)

After creating Kanban cards, **always** start auto-push immediately AND set up monitoring:

```python
# Step 1: Start kanban_await in background
result = terminal("cd ~/my_quant_system && python3 scripts/kanban_await.py T1 T2 T3 --timeout 600 &")
bg_id = result.get('session_id')

# Step 2: IMMEDIATELY start polling — background output won't auto-deliver
import time
for _ in range(12):  # poll up to 6 minutes
    poll = process(action='poll', session_id=bg_id)
    if poll.get('status') == 'exited':
        log = process(action='log', session_id=bg_id)
        # parse summaries from log['output']
        break
    time.sleep(30)
```

**Do NOT** just start `kanban_await.py` and wait. Background process stdout
does NOT flow into the conversation — you must actively poll.

### Review Gate (Every Phase, Auto-Trigger)

For every engine before calling it "done" — **and don't wait for the user to ask for a review**:

1. Write the engine code.
2. Run it on the latest trading day — verify it produces output.
3. **Auto-initiate 4-agent Kanban review** — the user's expectation is "finish a task → auto-review quality"
4. Use `kanban_await.py` for auto-push.
5. Read orchestrator synthesis → identify P0s.
6. Fix all P0s, re-run engine, re-verify.
7. Only then register the production cron.

## Common Bug Checklist (Check EVERY Engine)

- [ ] **Date formats**: Are you querying with `YYYY-MM-DD` but the table
  stores `YYYYMMDD` (or vice versa)? Check EVERY table's actual format.
  Handle both with `candidates = [date, date.replace('-', '')]`.
  - `leader_stocks`, `sector_rotation`, `market_temperature`: `YYYY-MM-DD`
  - `daily_kline.date`: `YYYY-MM-DD`
  - `daily_basic` Tushare API: `YYYYMMDD`
  - `sector_moneyflow_ths.trade_date`: `YYYYMMDD` (no dashes!)
  - `index_daily.trade_date`: `20260710` format
- [ ] **Units**: Is `north_total` in 万元 (×10000→亿)? Is PE 0-100 or 0-1?
  Is ROE in raw percent (15.2→0.152)? Always sample raw DB values.
- [ ] **Column names**: API returns `hgt/sgt/north_money`; DB table expects
  `north_sh_amount/north_sz_amount/north_total`. Always add `df.rename()`.
- [ ] **Try/except**: Engine `run()` must wrap in try/except with traceback.
  Data-missing paths must not crash. Every sub-function that queries SQL
  must handle `None`/empty results gracefully.
- [ ] **Transactions**: Any `DELETE + INSERT` batch must be inside
  `BEGIN...COMMIT` with `try/except/rollback`. No bare `to_sql(append)`.
- [ ] **API rate limits**: Tushare `daily_basic` is 1 call/hour per ts_code.
  Use `trade_date` batch query instead. `fina_indicator` needs 0.35s sleep.
  `stock_basic` is 1 call/min.
- [ ] **Stock code consistency**: `daily_kline.stock_code` = pure digits;
  `ths_member.con_code` = `000001.SZ`; `limit_up_pool.thscode` = `000001.SZ`.
  Use `strip_suffix()` before JOIN.
- [ ] **INSERT explosion**: Always `DELETE WHERE trade_date=?` before insert
  to keep row count stable. No appending without dedup.
- [ ] **Performance**: Measure before optimizing. 83k SQL fears often turn
  into 0.91s reality. N+1 queries in `_calc_ma_ratio` are OK at small scale
  (472 sectors × 0.91s = fine).
- [ ] **Zero-byte files**: `data/*.db` placeholders must be deleted.

## Pitfalls

- **Kanban `parents` deadlocks**: Never pass `parents=[...]` to orchestrator
  cards. One worker crash → orchestrator never promotes. Use no-parents
  pattern: create orchestrator card without parents, let it read worker
  results via `kanban show`.
- **Kimi worker crashes**: Kimi K2.7-code has ~2/9 crash rate in Kanban mode.
  `worker-kimi` config has fallback_providers chain to DeepSeek. If Kimi
  fails twice, switch to `worker-glm` or `delegate_task` for its tasks.
- **Tushare MCP vs SDK**: MCP tools and `ts.pro_api()` are separate auth
  paths. Scripts use SDK; on-demand queries can use MCP. Both consume the
  same API quota.
- **north_total column mapping**: The original hsgt_moneyflow data writes
  API column names (`hgt`, `sgt`, `north_money`), but newer cron data
  writes mapped names (`north_sh_amount`, `north_total`). Engine must handle
  both or force a column mapping in the cron script.
- **估价表v3.1模型空channel_position**: Old valuation model (v3.1) does not
  output channel_position. New `refresh_valuation.py` uses `daily_basic`
  PE history to compute it. Run refresh after any model version change.
- **周末/节假日 daily_basic 无数据**: `refresh_valuation.py` uses datetime.now()
  to pick today/yesterday, which hits non-trading days on weekends.
  Always pass the latest trading day or query it from trade_cal/daily_kline.
  Manually specify `--date 20260710` when running on weekends.
- **Leader stocks date format (the most common JOIN fail)**: `leader_stocks.trade_date`
  stores `YYYY-MM-DD`. `sector_moneyflow_ths.trade_date` stores `YYYYMMDD`.
  Always check each table's actual format before writing JOINs or WHERE clauses.
  When in doubt, sample `SELECT DISTINCT trade_date FROM table LIMIT 5`.
- **龙头股估值普遍高估 (empirical finding)**: Limit-up leader stocks often
  have channel_position in the 85-100% range (expensive). The three-layer
  system's valuation gate effectively prevents chasing the hottest names —
  the highest-scoring leaders get blocked by L3, while mid-scoring stocks
  with low channel_position (e.g. pos=17.5%) become the real buys.
- **Leader stock valuation coverage**: After P4, only self-selected stocks
  have valuation data. L2 leader stocks are mostly missing.
  Run `refresh_leader_valuation.py` (accepts `--date` and `--codes`)
  to extend coverage. Expect about 76% coverage; rest are loss-making.
- **估值扩展脚本用公共模块**: Both refresh scripts share `valuation_utils.py`
  (get_ts_code, calc_channel_position, rating_from_position,
  compute_safety_margin). Modify valuation logic in the shared module first.
- **PE history window**: Default is 3 years (1095 days). 1 year produced
  unstable channel positions. Don't shorten below 2 years.

## Verification

```sql
-- All three layers should have data for the latest trading day
SELECT 'L1', MAX(trade_date), COUNT(*) FROM market_temperature
UNION ALL
SELECT 'L2', MAX(trade_date), COUNT(*) FROM sector_rotation
UNION ALL
SELECT 'L3', MAX(trade_date), COUNT(*) FROM decision_log;

-- Leader stock valuation coverage
SELECT
  COUNT(*) as total_leaders,
  SUM(CASE WHEN v.channel_position IS NOT NULL THEN 1 ELSE 0 END) as covered
FROM leader_stocks l
LEFT JOIN valuation_results v ON l.stock_code = v.stock_code
WHERE l.trade_date = (SELECT MAX(trade_date) FROM leader_stocks);
```
