# Data Gap Discovery — A-Share Quant System Design

## Core Technique

When designing a new quant system module, **never assume existing data is sufficient**. Run a systematic gap analysis:

### Step 1: List Required Data by Module

| Module | Data Needed | Source |
|--------|-------------|--------|
| L1大盘温度 | index_daily, market_moneyflow, hsgt_moneyflow, limit_up_pool, two-rong margin | Tushare |
| L2板块轮动 | sector_moneyflow_ths, industry_moneyflow_ths, **ths_member**, limit_up_pool, limit_up_ladder, moneyflow_daily, daily_kline | Tushare + existing |
| L3个股估值 | valuation_results, daily_kline, daily_factors | existing |

### Step 2: Verify Each Data Source Exists

Query SQLite to check:
```sql
-- Check table existence + row count
SELECT name, rows FROM sqlite_master ... 

-- Check date range for time-series tables
SELECT MIN(trade_date), MAX(trade_date), COUNT(*) FROM sector_moneyflow_ths;

-- Check for specific critical tables
SELECT name FROM sqlite_master WHERE type='table' AND name='ths_member';
```

### Step 3: Verify Data Freshness

```sql
-- Most recent date
SELECT MAX(trade_date) FROM sector_moneyflow_ths;
SELECT MAX(trade_date) FROM market_moneyflow;
```

### Step 4: Critical Gaps Found in This Session

| Gap | Table | Issue | Impact | Fix |
|-----|-------|-------|--------|-----|
| **ths_member 缺失** | `ths_member` | 同花顺板块→成分股映射表完全不存在 | 无法做板块内均线多头占比分析、无法按板块聚合涨停数据 | 通过 Tushare MCP `ths_member` 回填全历史 |
| **板块资金流历史不足** | `sector_moneyflow_ths` | 仅1146行 ≈ 3天数据 | 无法计算连续N日资金流入天数趋势 | Hermes cron 回填60天 |
| **两融数据缺失** | 无 `margin` 相关表 | 融资余额变化数据不存在 | 杠杆资金情绪维度缺位 | Tushare `margin` 接口补充 |
| **估值覆盖不足** | `valuation_results` | 仅118条，不覆盖全市场 | L2龙头股可能无估值可用 | 优先覆盖自选股(154只) + L2板块龙头 |

## Resolved Gaps (P1 Infrastructure, 2026-07-09)

After Phase 1 data infrastructure buildout, the following gaps from the initial assessment were **resolved**:

| Gap | Resolution | Outcome |
|-----|-----------|---------|
| `ths_member` 缺失 | 通过Tushare批量采集885xxx(288概念)+886xxx(95新概念)+881xxx(90行业)=**472板块/71,398行** | ✅ L2板块内分析可行 |
| 板块资金流历史不足 | 回填80个交易日(20260310~20260706)：概念30,861行+行业7,200行=**38,061行** | ✅ 连续60日趋势判断可行 |
| 两融数据缺失 | 仍缺失 — P1优先级低，计划P2/P3补 | ⏳ 后续补充 |
| 估值覆盖不足 | 仍缺失 — 118条，后续优先覆盖自选股+L2龙头 | ⏳ 后续补充 |

## New Tables Created (P1 Infrastructure, 2026-07-09)

7 new tables created in stock_data.db for the 3-layer decision system:

| Table | Purpose | Key Fields |
|-------|---------|------------|
| `market_temperature` | L1大盘温度评分历史 | trade_date, temperature_score, index_trend_score, capital_flow_score, sentiment_score, position_ratio |
| `sector_rotation` | L2板块轮动评分 | (trade_date,sector_code), heat_score, rank, inflow_days, cumulative_net, leader_stock, stage |
| `leader_stocks` | L2龙头股候选池 | (trade_date,stock_code), leader_score, leader_type, board_count, channel_position |
| `decision_log` | 三层融合决策日志 | id PK, trade_date, decision_type, confidence, l1_temperature, l2_heat_score, l3_val_signal |
| `drawdown_log` | 风控回撤日志 | id PK, alert_level, alert_type, current_drawdown, action_taken |
| `valuation_daily_signal` | L3估值每日信号 | (stock_code,trade_date), channel_score, safety_score, valuation_signal |
| `valuation_sector_config` | 行业估值配置 | industry_name PK, primary_model(pb_roe/pe_band/peg/dcf), buy_threshold, sell_threshold |

## Critical Bug Found: valuation_sector_config Name Mismatch

During P1 review (worker-glm), discovered **52% of industry names** in `valuation_sector_config` don't match the actual names in `industry_moneyflow_ths`. Example: config says "交通运输" but real name is "机场航运"/"公路铁路运输". Fix: add `sector_code` column using 881xxx.TI codes as join key. See the P1 review report for full mapping.

### Pitfalls

- **"Zero new data" is a dangerous assumption**: DeepSeek agent initially claimed "zero new data needed" for the 3-layer system, but GLM agent discovered `ths_member` was critically missing. **Always cross-validate "existing data" claims with actual DB queries.** Each sub-agent independently verified its layer's data needs — this pattern caught the gap.
- **Row count ≠ data completeness**: `sector_moneyflow_ths` has 1146 rows which looks OK, but that's only ~3 days for ~380 sectors, not enough for trend analysis.
- **Table exists ≠ data is usable**: Check date range, not just row count.
