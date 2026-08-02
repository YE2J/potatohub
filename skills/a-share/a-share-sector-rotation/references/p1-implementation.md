# 三层决策系统 + 板块轮动数据管线 — 实施记录

> 2026-07-09 执行。基于 Tushare MCP + Hermes cron + stock_data.db (SQLite 6.9GB)

## Phase 1 执行记录

### 已创建脚本

| 脚本 | 路径 | 用途 |
|------|------|------|
| `migrations/004_create_three_layer_tables.sql` | `~/my_quant_system/migrations/` | 7张新表DDL + 25行行业估值配置 |
| `backfill_sector_moneyflow.py` | `~/my_quant_system/scripts/` | 回填80天板块资金流历史 |
| `daily_sector_moneyflow.py` | `~/my_quant_system/scripts/` | 每日板块资金流增量(no_agent cron) |

### 已注册Cron

| 名称 | 调度 | 类型 | 脚本 |
|------|:----:|:----:|:----:|
| 板块资金流向-每日增量 | `0 16 * * 1-5` | no_agent | `daily_sector_moneyflow.py` |

### 数据成果

| 表 | 行数 | 范围 |
|:---|:----:|:----:|
| `ths_member` | 71,398行 / 472板块 | 885xxx(288)+886xxx(94)+881xxx(90) |
| `sector_moneyflow_ths` | 30,861行 | 80天概念板块 |
| `industry_moneyflow_ths` | 7,200行 | 80天行业板块 |

## 缺失板块说明

以下7个板块在资金流数据中出现但跳过采集ths_member：
- `885338.TI` 融资融券 (3773只大盘股，非真实概念)
- `885598.TI` 新股与次新股 (过渡性)
- `885699.TI` ST板块 
- `885905.TI` 注册制次新股
- `885907.TI` 科创次新股
- `885916.TI` 同花顺漂亮100 (100只，可选)
- `886106.TI` 2025三季报预增 (无数据)

## 4Agent设计产出

| Agent | 文件 | 聚焦 |
|:-----|:----|:------|
| DeepSeek(架构师) | `docs/THREE_LAYER_ARCHITECTURE_PLAN.md` (854行) | 整体架构、数据流、三层顶层设计 |
| Kimi(趋势分析师) | `docs/market_temperature_system.md` (961行) | L1大盘温度 — 指数趋势35%+资金35%+情绪30% |
| GLM(板块轮动策略师) | `docs/sector_rotation_design.md` | L2板块轮动 — 资金连续流入+均线多头+龙头识别 |
| MiniMax(审计师/风控) | `audit_valuation_roadmap.md` (609行) | L3估值门控+6周迭代路线图+风控体系 |

各文件路径: `~/my_quant_system/`

## 关键发现

1. **所有L1/L2/L3数据在stock_data.db中已有**，无需新增外部数据源
2. **ths_member是P0缺失** — 无板块成分映射则L2板块内分析全部不可行
3. **资金流历史仅3天** — 需回填至少60天才能计算连续流入
4. **sqlite3 date格式陷阱** — `moneyflow_cnt_ths`返回的无横杠格式与原始cron的带横杠格式冲突
