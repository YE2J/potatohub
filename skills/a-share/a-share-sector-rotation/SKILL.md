---
name: a-share-sector-rotation
description: >-
  A股板块轮动数据分析基础设施 — 从数据采集（ths_member板块成分股映射、
  板块资金流向）、历史回填、每日增量cron，到L1-L3三层决策框架的搭建。
  Use when 用户要求做板块轮动分析、找热门板块、龙头股识别、设置板块资金流数据管线、
  或搭建三层决策系统（大盘温度→板块轮动→估值门控）。
---

# A股板块轮动数据基础设施

> 基于 Tushare MCP + Hermes cron 的全链路板块数据分析管线

## 数据管线概览

```
Tushare MCP / Python SDK
    │
    ├── ths_index(type=N) → 概念板块列表 (885xxx.TI, 886xxx.TI)
    ├── ths_index(type=I) → 行业板块列表 (881xxx.TI)
    ├── ths_member(ts_code) → 板块→成分股映射表 (ths_member表, 472板块/71K行)
    │
    ├── moneyflow_cnt_ths(date) → 同花顺概念板块资金流 (sector_moneyflow_ths表, 万元)
    ├── moneyflow_ind_ths(date) → 同花顺行业板块资金流 (industry_moneyflow_ths表, 万元)
    ├── moneyflow_ind_dc(date, type=概念/行业) → 东方财富板块资金流 (sector_moneyflow_dc / industry_moneyflow_dc表, 元)
    ├── margin(trade_date, exchange_id) → 融资融券余额 (margin_balance表)
    ├── moneyflow_mkt_dc(date) → 大盘资金流 (market_moneyflow表)
    ├── moneyflow_hsgt(date) → 北向资金 (hsgt_moneyflow表)
    └── index_daily → 5指数日线
            │
            ▼
    ┌───────────────┐
    │  stock_data.db │
    │  SQLite 6.5GB  │
    └───────┬───────┘
            │
    ┌───────┴──────────────────────┐
    │                              │
    ▼                              ▼
  L1: engines/market_temperature.py   L2: engines/sector_rotation.py
  (大盘温度评分, 3维度合成)            (板块热度评分+龙头识别)
       │                                    │
       └────────────────┬───────────────────┘
                        ▼
                  L3: engines/decision_fusion.py
                  (决策融合: 温度→仓位门控 + 估值→买入/卖出信号)
```

## 每日数据管道时间线

```
18:00  前复权日线 + 指数日线 (批量cron)
18:30  大盘资金流 + 北向资金 (daily_market_moneyflow.py)
18:35  两融余额 (daily_margin_balance.py) 🆕
18:45  同花顺概念+行业板块资金流 (daily_sector_moneyflow.py, THS)
18:50  东方财富概念+行业板块资金流 (daily_sector_moneyflow_dc.py, DC)
19:00  大盘温度计算 L1 (engines/market_temperature.py)
20:00  板块轮动 L2 (engines/sector_rotation.py) → DC v2
20:30  决策融合 L3 (engines/decision_fusion.py)
```

## 引擎架构

### L1: 大盘温度引擎 (`engines/market_temperature.py`, ~680行)

类 `MarketTemperatureEngine`:
- `calc_index_trend(date)` → 5指数均线排列(60%)+价格位置(30%)+MACD(10%)
- `calc_capital_flow(date)` → 主力资金(50%)+北向(35%)+两融(15%)
- `calc_sentiment(date)` → 涨跌比(35%)+涨停数(25%)+连板(15%)+量能(25%)
- `run(date)` → 合成写入 `market_temperature` 表

**关键修复**:
- hsgt_moneyflow `north_total` 单位万元→亿元
- 日期兼容 `YYYY-MM-DD` 和 `YYYYMMDD` 双格式
- MACD用 `pandas.ewm(adjust=False)`替代SQLite SMA
- 仓位映射 T=65~80 渐变(无悬崖), T=80~100 从60%渐降到0%
- 跌停从 `daily_kline` 估算(limit_up_pool只有涨停)

### L2: 板块轮动引擎 (`engines/sector_rotation.py`, ~550行)

类 `SectorRotationEngine`:
- `calc_sector_heat(date)` → 991板块全量（DC），5维度合成热度评分
- `identify_leaders(date, top_sectors)` → 三级龙头(涨停/资金/趋势)，DC/THS双源交叉验证
- `run(date)` → 写入 `sector_rotation` + `leader_stocks` 表

**评分维度**: 资金连续流入(30%)+斜率(15%)+涨幅(15%)+均线多头占比(25%)+龙头强度(15%)

**数据源切换**: 通过 `DATA_SOURCE = 'dc'` 常量控制，支持 `'dc'` (东方财富) 和 `'ths'` (同花顺)：
- DC模式：读 `sector_moneyflow_dc`/`industry_moneyflow_dc` 表，`net_amount/1e4` 归一化，MA占比固定0.5（中性，因DC代码与ths_member不兼容）
- THS模式：读 `sector_moneyflow_ths`/`industry_moneyflow_ths` 表，通过 `ths_member` 计算MA占比

**龙头识别双源交叉验证**:
- DC板块代码(.DC) → 查 `dc_member` 表 → 同一股票也在 `ths_member` 中 → 标记交叉验证通过(+20分)
- THS板块代码(.TI) → 查 `ths_member` 表 → 同一股票也在 `dc_member` 中 → 标记交叉验证通过(+20%)
- 写入 `leader_stocks` 表时包含 `cross_validated` 和 `data_source` 字段

**阶段判断**: 连续≥5日→主战场, ≥3→潜力, 其余→观察

### L3: 决策融合引擎 (`engines/decision_fusion.py`, ~320行)

类 `DecisionFusionEngine`:
- `run(date)` → 读L1温度→仓位限制→读L2龙头候选→估值门控→写入 `decision_log`
- 估值门控: `channel_position ≤ 35`→买入(需safety_margin≥-20%), `≥85`→卖出
- 信号权重: 买入+30, 卖出-50, watch保持0
- 仓位上限: 空仓(≤5%)→0只, 重仓(≥80%)→最多10只

## 关键数据表

### 1. ths_member — 板块-成分股映射表
```sql
  ts_code   TEXT PRIMARY KEY   -- 板块代码 (e.g. 885431.TI)
  con_code  TEXT PRIMARY KEY   -- 成分股代码 (e.g. 000009.SZ)
  con_name  TEXT               -- 成分股名称
```
- **来源**: `pro.ths_member(ts_code='xxx.TI')`
- **覆盖**: 概念板块(885xxx/886xxx) + 行业板块(881xxx) ≈ 472板块
- **用途**: L2板块内均线向上占比计算、龙头股板块归属映射

### 2. sector_moneyflow_ths — 同花顺概念板块资金流（已降级为辅助源）
- **来源**: `pro.moneyflow_cnt_ths(trade_date='YYYYMMDD')`
- **用途**: L2板块连续资金流入天数、累计净流入
- **⚠️ 单位**: `net_amount` 存储为 **万元**，转亿需除 1e4。数据量级偏小（日均~0.01~0.05亿），**仅适合看方向**，不适合做资金量分析。详见 `references/ths-moneyflow-data-format.md`

### 3. industry_moneyflow_ths — 同花顺行业板块资金流
- **来源**: `pro.moneyflow_ind_ths(trade_date='YYYYMMDD')`
- **用途**: L2行业级别交叉验证
- **⚠️ 单位**: 同上，万元级

### 4. sector_moneyflow_dc — 东方财富概念板块资金流（主数据源，v2）
```sql
  trade_date, sector_code, sector_name, pct_change, close_price,
  net_amount(元), net_amount_rate, buy_elg_amount, buy_lg_amount, ...
```
- **来源**: `pro.moneyflow_ind_dc(trade_date='YYYYMMDD', content_type='概念')`
- **回填**: 2026-01-05 ~ 07-16 (128天)，脚本 `backfill_sector_moneyflow_dc.py`
- **优点**: 数据量级真实（单板块几十~上百亿/天），板块覆盖更全（441~500个/天）
- **用途**: L2板块轮动的资金维度首选源

### 5. industry_moneyflow_dc — 东方财富行业板块资金流
- **来源**: `pro.moneyflow_ind_dc(trade_date='YYYYMMDD', content_type='行业')`
- **分类粒度**: 496~510个细分类（vs THS行业仅90个粗分类）
- **⚠️ content_type 参数**: 必须用 `'概念'` 和 `'行业'`，不要加"板块"后缀（`'概念板块'` 返回空数据且无报错）

### 6. dc_member — DC板块-成分股映射表
```sql
  ts_code   TEXT   -- 板块代码 (e.g. BK0490.DC)
  con_code  TEXT   -- 成分股代码 (e.g. 000001.SZ)
  con_name  TEXT   -- 成分股名称
```
- **来源**: `pro.dc_member(ts_code='BKxxxx.DC', trade_date='YYYYMMDD')`
- **覆盖**: TOP150最活跃板块（按出现天数排序），约2,500行
- **用途**: L2龙头识别中DC板块的成分股查找 + DC/THS双源交叉验证
- **注意**: 成分股快照基于单日(当前使用20260716)，长期使用需定期更新

### 7. margin_balance — 两融余额（融资融券）
```sql
  trade_date  TEXT   -- 交易日
  exchange_id TEXT   -- SSE上交所 / SZSE深交所 / BSE北交所
  rzye        REAL   -- 融资余额
  rzmre       REAL   -- 融资买入额
  rzche       REAL   -- 融资偿还额
  rqye        REAL   -- 融券余额
  rzrqye      REAL   -- 融资融券余额
```
- **来源**: `pro.margin(trade_date='YYYYMMDD', exchange_id='SSE'/'SZSE'/'BSE')`
- **覆盖**: 全2026年历史（128交易日），脚本 `backfill_margin_balance.py`
- **cron**: 每日 18:35，`daily_margin_balance.py`
- **晨报**: `report_margin_balance()` 按交易所展示 + 较上日变动

### 8. 三层决策新表 (migrations/004_create_three_layer_tables.sql)
```sql
  market_temperature       -- L1大盘温度评分历史
  sector_rotation          -- L2板块轮动评分
  leader_stocks            -- L2龙头股候选池
  decision_log             -- 三层融合决策日志
  valuation_daily_signal   -- L3估值每日信号
  drawdown_log             -- 风控回撤日志
  valuation_sector_config  -- 行业估值配置(25行默认值)
```

## 常见问题

### P1. 数据格式不一致
`sector_moneyflow_ths` 原数据可能有 `YYYY-MM-DD` 和 `YYYYMMDD` 混合格式。
**修复**: 统一删除带横杠的老数据（已被YYYYMMDD覆盖）。回测脚本中宽表（moneyflow_daily/daily_kline）使用 `YYYY-MM-DD`，板块资金流表使用 `YYYYMMDD`。统一用 `fmt_date()` 函数互转。

### P2. 板块分类层次
同花顺板块分三级:
- **概念板块** (885xxx.TI, 886xxx.TI) — 适合轮动分析, ~382个
- **行业板块** (881xxx.TI) — 申万-like分类, ~90个
- **子行业** (884xxx.TI) — 太细, 可选

### P3. 资金流数据时效
Tushare 的 `moneyflow_cnt_ths` 每天盘后约17:00~18:00更新。`moneyflow_ind_dc` 同样盘后更新。
cron设在 `45 18 * * 1-5`（板块资金流）和 `30 18 * * 1-5`（大盘资金流）。

### P4. Tushare content_type 参数值（DC高频踩坑）
`moneyflow_ind_dc` 的 `content_type` 必须传 `'概念'` 和 `'行业'`（无"板块"后缀）。
传 `'概念板块'` 会返回空数据但无错误提示，难排查。
**排查技巧**: 回填全部返回"API返回空数据"时先检查 content_type。

### P5. net_amount 单位：DC 与 THS 不同
| 数据源 | 存储单位 | 转亿公式 | 典型值 | 适合用途 |
|:------|:--------|:--------|:------|:--------|
| THS `*_moneyflow_ths` | **万元** | ÷ 1e4 | ~0.01~0.05亿 | 方向判断 |
| DC `*_moneyflow_dc` | **元** | ÷ 1e8 | ~50~130亿 | 资金量分析 |
引擎内部 DC ÷ 1e4 归一化到万元再计算。

### P6. 引擎数据版本标记
`sector_rotation.data_version`:
- `v1` = THS（旧，472板块，万元级失真）
- `v2-dc` = DC（当前，991板块，量级真实）

### P7. Lambda闭包参数命名陷阱（回填脚本高频bug）
用 lambda 包裹 Tushare API 回调时，参数名必须与调用方的 keyword 匹配。
**最佳实践**: `_call_with_retry` 统一用位置参数传 date，lambda 内部再转 keyword 调 Tushare。

### P8. 回填脚本通用模板
回填脚本应包含（见 `backfill_sector_moneyflow_dc.py`）：
- 独立 try/except（概念/行业分开）
- `call_with_retry`: 3次重试 + 指数退避 2s→4s→8s
- `socket.setdefaulttimeout(30)` 防 API hang
- 信号处理器 `signal.signal(SIGINT/SIGTERM, cleanup)` 防 WAL 锁残留
- 连接追踪 `_open_conns` 列表
- 行数阈值校验（概念≥200行，行业≥50行）
- 双表独立缺失检测（避免概念表有数据时行业表也拉取）

### P9. moneyflow_daily 资金列名：`net_mf_amt` 而非 `main_net_amt`
`moneyflow_daily` 表的 `main_net_amt` 列全部为 NULL（Tushare DC 增量管线不写入此列）。
有效的个股主力净流入列是 **`net_mf_amt`**。
排查技巧: 查龙头股资金流时如返回全空，先确认用的列名是否正确。

### P10. 晨报版本文档
当前晨报使用 `daily_morning_report_v6.py`（v6.0），数据源切换为 DC（东方财富）。
- 晨报cron: `3cb6fbcc8dcc`（每日07:05，agent模式，推送微信）
- v5→v6变更: THS→DC板块表，资金量级万元→亿级，新增DC cron监控，新增两融余额+大盘温度模块，修复trade_cal重复行导致的连续天数翻倍
- 非交易日判定: 通过 trade_cal 动态放宽数据时效阈值，非交易日不报"通道异常"
- 截断优先级（高→低）: 板块资金流(1) > 两融余额(2) > 大盘温度(3) > 昨日任务(4) > 采集状态(5)
- 温度模块: `report_market_temperature(conn=None)` 复用build_report传入的conn；交易日展示三维分解+规则分析+建议；非交易日提示无更新+最新温度；conn泄漏由close_conn守卫

**cron验证清单（修改管线后必做）**:
1. `chmod +x ~/.hermes/scripts/*.sh` — 所有shell脚本必须可执行，否则cron静默失败（exit 126被误报为ok）
2. 脚本文件路径: no_agent cron 从 `~/.hermes/scripts/` 搜脚本，不在那里就建桥接wrapper（`.sh` 文件）或软链
3. `workdir` 只设CWD**不影响**脚本搜索路径 — 引擎脚本在 `~/my_quant_system/engines/` 需软链到 `~/.hermes/scripts/engines/`
4. 每次加新cron后，列出所有cron状态确认无 error（`cronjob action=list | grep error`）
5. 新增cron后24小时验证数据是否真的写入DB（不只检查status=ok，要查表行数）
6. 两融余额脚本的token保护：`token = None` 用完即清 + `try/except` 不打印异常详情

### P11. 回测脚本常见bug
1. **日期格式**: `moneyflow_daily.date` 是 `YYYY-MM-DD`，`daily_kline.date` 也是 `YYYY-MM-DD`，但 `sector_moneyflow_ths.trade_date` 是 `YYYYMMDD`。需统一用 `fmt_date()` 转换。
2. **`moneyflow_daily.close` 不存在**: 股价只能从 `daily_kline` 单独查询。
3. **`_calc_stats` 返回 `'trades': n` 但 `run_all` 中误写为 `'trades': trades`**: 列表赋值导致 `:>5` 格式化报错。
4. **过滤指数型板块**: 回测时 EXCLUDE_SECTORS 列表必须包含融资融券/沪股通/深股通/MSCI等宽基板块。
5. **最佳参数**: H20_T3（持有20天，每板块Top3龙头）— 胜率73.4%，夏普1.69，盈亏比6.77。

### P12. 两融余额（融资融券）引擎集成
**数据表**: `margin_balance`，全2026年历史回填完毕，每日18:35 cron增量更新。

**L1 大盘温度集成**（`engines/market_temperature.py`）:
- `calc_capital_flow()` 资金面维度中，两融占 **15%** 权重
- 评分逻辑: 较前日变动>+0.2%→加杠杆加分，<-0.2%→去杠杆扣分，中间→中性
- 与主力资金方向一致性: 两融+主力同向加5分/异向减5分
- 原代码是 stub（固定50分），已改为实际查询 `margin_balance` 表

**L2 龙头评分乘数**（`engines/sector_rotation.py`）:
- `identify_leaders()` 最终评分乘以 `self._margin_adj`:
  - 两融日增 > 0.2% → 乘 **1.15**（加杠杆环境，龙头溢价）
  - 两融日增在 -0.2% ~ 0.2% → 乘 **1.0**（持平）
  - 两融日增 < -0.2% → 乘 **0.85**（去杠杆环境，龙头折价）
- 在 `run()` 中 Step 2.5 计算乘数

**晨报集成**:
- `report_margin_balance()` 模块展示三所两融明细 + 全市场合计 + 较上日变动
- 以 `💰 两融余额` 标题排在板块资金流之后
- 截断优先级: 板块资金流(1) > 两融余额(2) > 大盘温度(3) > 昨日任务(4) > 采集状态(5)

## Support Files

- `references/ths-moneyflow-data-format.md` — THS 板块资金流数据格式、单位说明、列映射、已知坑
- `references/backfill-sector-moneyflow.md` — THS 回填策略与实现笔记
- `references/dc-vs-ths-data-comparison.md` — 东方财富 vs 同花顺 板块资金流交叉对比
- `references/p1-implementation.md` — P1实施记录
- `references/backtest-sector-leader.md` — 回测框架设计、参数对比、关键Bug修复记录
- `scripts/top5_sector_ranking.py` — 每日概念/行业板块TOP5净流入上榜次数统计
- `scripts/top5_sector_ranking_dc.py` — DC数据源TOP5净流入上榜排名
- `scripts/top5_sector_outflow_dc.py` — DC数据源TOP5净流出上榜排名
- `scripts/dc_ths_cross_compare.py` — DC vs THS 交叉对比工具
- `scripts/backfill_sector_moneyflow_dc.py` — DC板块资金流历史回填
- `scripts/daily_sector_moneyflow_dc.py` — DC板块资金流每日增量采集
- `scripts/daily_margin_balance.py` — 两融余额每日增量采集
- `scripts/backfill_margin_balance.py` — 两融余额全历史回填
- `scripts/backtest_sector_leader.py` — 板块TOP3上榜后龙头股持有期回测框架
- `scripts/leader_weekly_performance.py` — 板块TOP3上榜后龙头股一周表现分析
