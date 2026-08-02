---
name: a-share-quant-backtest
description: "A股量化回测与策略开发：数据获取 → 指标计算 → 策略引擎 → 回测评估。统一架构于 ~/my_quant_system/，覆盖同花顺/通达信公式的严格Python翻译、SQLite+Parquet数据层、规则引擎策略设计。"
version: 2.11.0
author: Hermes Agent
tags: [a-share, backtest, quantitative, strategy, tonghuashin, tdx, coze-integration, ths-moneyflow, screening, multi-day]
last_updated: 2026-07-05
---

# A股量化回测与策略开发

## 触发条件

当用户提到：量化回测、写策略、回测指标、python回测、指标评估、信号生成、策略引擎、backtest、v4回测、GS信号、主力雷达 等。

## 用户偏好

- **公式翻译必须严格保留原逻辑** — 通达信/同花顺的公式语言（SMA公式参数、CROSS语义、AND/OR优先级）必须逐行精确复现，不允许"简化"或"优化"原版计算。
- **数据源优先使用已入库的 SQLite** — 避免实时 API 调用，DB 已有 2.2GB 覆盖。`daily_kline`（前复权）→ `moneyflow_daily`（THS资金流）→ `cyq_*`（筹码）→ `hk_hold`（港通）→ `ind_moneyflow`（板块）。
- **晨报聚焦数据质量** — 只展示三类数据：**📈 日线状态**（最新日期/覆盖/自选涨跌TOP3）、**💰 资金流向**（日期/覆盖/来源/量额完整度/主力净流入TOP5）、**⚙️ 系统运维**（一行摘要）。砍掉所有中间环节（同步/cron/文件状态）的琐碎信息。用户原话："数据的质量才是我重点关注的"。
- **🆕 实施前必须走三方评审流程** — 任何涉及数据源、策略、指标、架构的改动，必须先写方案→3个Agent并行评审（数据完整性/兼容性/架构部署三个维度）→汇报结论→用户决策→再动手。禁止看到用户说"就这样做"就跳过评审直接改代码。除非改动极简单（单文件单函数、无数据流影响）。
- 暗盘资金和主力持仓指标**代码已存在于 strategy_library**，标记为 `available`/`degraded` — 有 Tushare 数据时可激活，不可得时降级运行。
- **所有工作基于统一系统 `~/my_quant_system/`** — 旧系统已删除，不要再引用。
- **所有导入使用 `strategy_library.indicators`** — `indicators_tdx.py` 是向后兼容 wrapper，新代码不要直接从它导入。

## 🖼️ 回测报告生成（--report 参数）

`backtest_v4.py` 支持 `--report` 参数生成独立 HTML 报告：

```bash
~/.pyenv/versions/3.11.11/bin/python3 backtest_v4.py --report
```

**`backtest_report.py`** — 纯 Python + SVG 报告生成器，**零额外依赖**（不需要 plotly/matplotlib）。

报告包含：
- 10 项关键指标卡片（总收益率/年化/夏普/回撤/卡玛/胜率/盈亏比/交易次数/平均每笔收益/最终权益）
- 📈 收益曲线 vs 沪深300（SVG 折线图）
- 📉 回撤曲线（SVG 填充区域图）
- 📅 月度收益热力图（SVG 色块矩阵）
- 📊 年度收益汇总表（HTML table）
- 📦 单票盈亏分解条形图
- 🎯 每笔交易盈亏分布

输出：`results/backtest_report_{timestamp}.html`，深色主题，可离线用浏览器打开。

基准对比（沪深300）：自动从 `index_daily` 表加载 `000300.SH` 数据。数据来源为东方财富免费 API（push2his.eastmoney.com），无需 Tushare 积分。

**技术原理**：全部使用原生 Python 字符串拼接 + SVG 标签生成矢量图形。六个图表函数分别是 `render_equity_curve()`, `render_drawdown()`, `render_monthly_heatmap()`, `render_bar_chart()` 等。没有任何第三方图表库依赖。

**沪深300基准对齐**：使用**日期对齐**（`dict(zip(bench_dates, bench_values))` 按日期取对应值），不能用数组索引直接对齐——因为 equity_curve 和 HS300 数据长度不同。数据源为东方财富免费 API（push2his.eastmoney.com），不要用 Tushare index_daily（限频 1次/小时）。脚本：`scripts/import_hs300_v2.py`。

**关键字段**：`run_multi_backtest()` 现在返回 `"dates"` 字段——`[str(d.date()) for d in all_dates]`，基准对齐依赖这个字段。

## 🔬 策略修复影响的审查方法

当策略或筛选条件被修复后（如 ST 排除、覆盖率日志、窗口动态化），必须用 Systematic Regression Review 验证修复的**实际效果**，而非仅确认代码改"对"了。以下框架基于 2026-07-03 对 screen_v4.py 和 backtest_v4.py 的完整审查经验：

### 审查五维度

| # | 维度 | 核心问题 | 验证方法 |
|---|------|---------|---------|
| 1 | **ST排除效果** | 修复后是否有效排除 ST/退市股？排除数量符合预期？ | `factor_table` 查 ST 数量，运行 screen 对比前后 4条件命中数 |
| 2 | **覆盖率帮助** | 覆盖率日志是否让用户能判断数据质量？ | 检查覆盖率打印在 `backtest_v4.py` (每只+汇总) 和 `screen_v4.py` (缺失) |
| 3 | **窗口一致性** | 因子表模式和回退模式使用同一数据范围吗？ | 对比 `screen_from_factors` 的 `_prev_trade_date()` 与 `screen_fallback` 的 180天/60天窗口 |
| 4 | **误杀风险** | 排除逻辑会错杀非ST股吗？ | 检查 `is_st_stock()` 逻辑 + 扫描 all_ashare_stocks.csv 确认 0 误杀 |
| 5 | **交易可操作性** | 修复后信号数量是否合理（可执行）？ | 统计 4条件命中数，若 >10 只说明需要二级排序 |

### 验证流程

```bash
# Step 1: 运行当前筛选，记录数字
~/.pyenv/versions/3.11.11/bin/python3 screen_v4.py --date 2026-06-26

# Step 2: 手动查 daily_factors 的 ST 分布
sqlite3 stock_data.db "SELECT COUNT(*) FROM daily_factors WHERE trade_date='2026-06-26'"
# 再查 name_map 中 ST 数量

# Step 3: 检查覆盖率日志（backtest 模式）
~/.pyenv/versions/3.11.11/bin/python3 backtest_v4.py 2>&1 | grep "因子覆盖"

# Step 4: 检查误杀 — 遍历 name_map 确认无非ST名含"ST"
python3 -c "
import csv
with open('all_ashare_stocks.csv') as f:
    for r in csv.DictReader(f):
        n = r['SecuAbbr']
        if 'ST' in n.upper() and not (n.startswith('*ST') or n.startswith('ST')):
            print(f'潜在误杀: {r[\"SecuCode\"]} {n}')
"

# Step 5: 信号过多时评估可操作性
# 23只超过 max_positions=3 → 需增加成交额或暗盘强度二次排序
```

### 典型发现模式

- **ST排除**：A股 ST 占 ~4%（200-300只），排除后 4条件命中通常减少 1-5 只
- **覆盖率 <50%**：回测结果标记为不可靠，需先补因子数据再回归
- **窗口不匹配**：因子表用的是 Tushare adj 数据，回退模式用的是 Coze 不复权数据 → 除权日差异
- **信号密度**：4条件全匹配通常在 20-60只/日，需结合 `backtest_v4.py` 的 3只上限 + 主力线上涨幅度排序

### 输出格式

最终以结构化表格报告五个维度的评分（⭐⭐⭐⭐☆ 格式）和具体数字证据。

**禁止看到用户说"就这样做"就直接改代码。** 这是 2026-06-24 的教训：系统的致命问题（dz_dailyquote 不复权→假信号）就是因为在方案评审阶段被抓出来的。任何涉及数据源、指标、策略、架构的改动，必须先：

1. 写方案（数据流、fallback、边界情况）
2. **3 个 Agent 并行评审**：一个看数据完整性、一个看兼容性+异常、一个看架构+部署
3. 汇报评审结论
4. **用户决策后**再实施

只有在改动极简单（单函数单文件、无数据流影响、无下游依赖）时可豁免。

## 项目位置

```
~/my_quant_system/                          ← 唯一量化系统
├── config.py                               ← 全局配置（STOCKS_V4 99只, V4_PARAMS）
├── data_manager.py                         ← SQLite + Parquet（含 load_to_dataframe）
│
├── strategy_library/                       ← 🆕 策略武器库（真相源）
│   ├── _core.py                            ← TDX核心函数（15个，纯NumPy）
│   └── indicators/
│       ├── __init__.py       ← 公开导入所有 calc_xxx 函数
│       ├── _zhuli_radar.py   ← 主力雷达
│       ├── _ai_activity.py   ← AI活跃度
│       ├── _gs_signal.py     ← GS信号
│       ├── _dark_pool.py     ← 暗盘资金（🟠 降级：K线估算 → 完整：Tushare≥2000积分）
│       └── _zhuli_holdings.py ← 主力持仓（🟠 降级：DDX递推 → 完整：同花顺LV2）
│   └── adapters/
│       └── moneyflow.py      ← 资金流适配器（DB读→降级估算→THS列映射）
│
├── indicators_tdx.py                       ← 向后兼容 wrapper（→ strategy_library）
├── strategies_v3.py                        ← v3 规则引擎
├── backtest_v4.py                          ← v4 多票组合引擎（--report 参数支持生成HTML报告）
├── backtest_report.py                     ← 🆕 纯 Python SVG 回测报告生成器（零依赖）
├── bridge.py                               ← 桥接：DB→指标→回测→DB保存
├── analyze_losers.py                       ← 亏损诊断
├── screen_v4.py                            ← 🆕 全A股条件筛选（N条件扫描，返回候选池表）
├── screen_monthly_validation.py            ← 🆕 多日扫描+信号后表现追踪（月度验证）
├── debug_screen.py                         ← 🆕 全A股扫描调试助手
│
├── strategy_library/                       ← 策略武器库（真相源）
│   ├── evaluation/                          ← 🆕 因子IC评估模块（ic_analyzer.py，纯pandas）
│   │   ├── __init__.py
│   │   ├── ic_analyzer.py                  ← IC/ICIR/分层回测/衰减/相关性矩阵+HTML报告
│   │   └── vendor/
│   │       └── chart.umd.min.js            ← Chart.js v4.4.0 离线版
│   ├── factors.py                          ← 🆕 因子表管理（batch_load/compute/query/batch_upsert）
├── scripts/                                ← 系统脚本
│   ├── import_daily_factors.py             ← 🆕 每日因子导入（CLI: init/daily/backfill/validate）
│   ├── coze_incremental_update.py           ← Coze 增量（01:05 cron）
│   ├── pull_adj_factors.py                  ← 🆕 复权因子批量拉取（Tushare API）
│   └── batch_valuation.py                  ← 批量估值
│
├── indicators.py                           ← 旧 backtrader SMA/EMA/ATR
├── strategy.py                             ← 旧 backtrader MyStrategy（demo）
│
├── stock_data.db                           ← SQLite（53MB, 14表）
├── data/parquet/                           ← Parquet 缓存
├── .venv/                                  ← Python 3.9
│
└── app/main.py                             ← FastAPI（+v4/v3 API routes）
```

VENV: `~/my_quant_system/.venv/bin/python`（Python 3.9）

## 核心架构

```
数据层(SQLite+Parquet) → bridge.py → 指标层 → 策略层 → 回测层 → DB保存
```

**关键设计**：策略引擎（indicators_tdx, strategies_v3, backtest_v4）保持纯 pandas/NumPy 向量化，**不转 backtrader**。bridge.py 在数据输入（从 DB 读 DataFrame）和结果输出（写 v4_backtest_results 表）两个点做薄适配，策略逻辑一行不改。

### 1. 数据层 — 统一 Coze（恒生聚源）+ 前复权修复

**2026-06-24 最终版**：日线数据统一从 Coze 管道（恒生聚源）读取，覆盖 5,527 只全 A 股。已修复不复权→前复权的致命问题。

- **主数据源**：`dz_dailyquote` 表（恒生聚源，Coze 每日增量写入）
  - 覆盖 5,527 只 A 股，日期范围 2025-06-23 起
  - ⚠️ 恒生聚源存储的是**不复权原始价**，不可直接用于通达信指标计算
  - 系统 crontab `01:05` 执行 `coze_incremental_update.py` 自动增量（含 PAT 到期检测 + 90 天自动清理）
  - InnerCode ↔ stock_code 映射通过 `all_ashare_stocks.csv` 自动加载（已做静态缓存，进程生命周期内只读一次）
- **复权修复**：`adj_factors` 表（Tushare 复权因子）
  - `_load_from_dz_dailyquote()` 中自动 LEFT JOIN `adj_factors`，计算 `adjusted_price = raw_price × adj_factor`
  - PrevClosePrice 用前一日 adj_factor 调整后重算 pct_change/change/amplitude
  - adj_factor 缺失时回退原始价格 + log warning
  - Volume 不做复权（成交股数不受除权影响）
  - 批量拉取：`pull_adj_factors.py --codes` 或 `--all`
- **历史 fallback**：`daily_kline` 表（腾讯 API / Coze QFQ，前复权，2019-12-31 ~ 今，5,874 只）
  - ⚠️ `daily_kline` 的数据已经是前复权的（Coze 腾讯 fqkline API 直接返回前复权价），**不需要 adj_factors 再次复权**
  - 所以回测中显示的 "adj_factors 表无数据" 警告仅仅是 dz_dailyquote 路径报的，**不影响 daily_kline 路径的前复权准确性**
- **最终 fallback**：`data/parquet/`（极旧备份）
- **最终 fallback**：`data/parquet/`（极旧备份）
- **加载链路**：`dz_dailyquote × adj_factor → daily_kline → Parquet`，返回前复权 OHLCV + 衍生字段

**日期格式注意**：`dz_dailyquote.TradingDay` 存 `YYYY-MM-DD`（带横线），查询时必须转换参数格式，否则 SQLite 字符串比较错误。
资金流数据：

- **同花顺 THS（主力）**：`moneyflow_daily` 表，`data_source='ths'`
  - 14,232,762 行，5,663 只 A 股，2007-01-04 ~ 2026-06-26
  - 四档（小单/中单/大单/特大单）买入卖出量（手）+ 额（万元），逐行净流入已算好
  - 来源：`~/Documents/quant-data/moneyflow/` 目录 CSV 文件全量导入
  - 不再使用东方财富或问财 API 作为主力数据源
- **东方财富（备胎）**：`data_source='eastmoney'`，仅 31 行存量数据，保留做历史对比用\n- **Tushare DC（增量）**：`data_source='tushare_dc'`，11,152 只, 2026-06-29~今。仅含 net 量(lg_net_amt/elg_net_amt等)，**不含分档买卖金额**，不可用于暗盘资金和主力持仓计算。仅 GS/雷达/AI 等纯OHLCV指标可用。
- 详见 `references/ths-moneyflow-import.md`（已更新，2026-06-29 版本覆盖东方财富管线）

### 2. 指标层 — strategy_library（真相源）

**所有新代码从 `strategy_library.indicators` 导入。`indicators_tdx.py` 是向后兼容 wrapper。**

TDX 核心函数在 `strategy_library/_core.py`，各指标在 `strategy_library/indicators/_*.py`。

**5个指标**（3个 active + 2个待数据）：

| # | 函数 | 模块 | 状态 | 数据需求 |
|---|------|------|------|---------|
| 1 | `calc_zhuli_radar(df)` | `_zhuli_radar` | ✅ active | 仅 OHLCV |
| 2 | `calc_ai_activity(df)` | `_ai_activity` | ✅ active | 仅 OHLCV |
| 3 | `calc_gs_signal(df)` | `_gs_signal` | ✅ active | 仅 OHLCV |
| 4 | `calc_dark_pool(df, mf_df)` | `_dark_pool` | ✅ active | moneyflow_daily |
| 5 | `calc_zhuli_holdings(df, mf_df)` | `_zhuli_holdings` | ✅ active | moneyflow_daily |

**⚠️ 输出列名大坑（2026-07-01 踩过）**：
- `calc_zhuli_holdings` → 输出列是 **`zhuli_holding`**（单数），不是 `zhuli_holdings`！另有 `zhuli_ddx_daily`
- `calc_dark_pool` → 暗盘净额列是 **`dark_pool_1d`**（3d/5d），流入信号列是 **`dark_pool_inflow_signal`**（布尔）
- 详见 `references/screening_methodology.md`

**调用方式**：
```python
# 正确 ✅
from strategy_library.indicators import calc_zhuli_radar, calc_gs_signal

# 兼容 ✅（deprecated）
from indicators_tdx import calc_zhuli_radar
```

**策略注册表**（`strategy_library/_catalog.py`）：
```python
from strategy_library import catalog
catalog.print_catalog()        # 打印完整目录
catalog.list_indicators()      # 列出所有指标
catalog.get_indicator("zhuli_radar")  # 动态加载
```

**添加新指标步骤**：
1. `strategy_library/indicators/_new.py` — 实现 `calc_new(df) → df`
2. `strategy_library/indicators/__init__.py` — 导入
3. `strategy_library/_catalog.py` `INDICATORS` dict — 注册

### 3. 策略层

#### v3 规则引擎（`strategies_v3.py`, ~538行）

单票打分制，五层架构。输出 `conviction` (7级: strong_buy → strong_sell) → `position_target` (7档: 100% → -100%)。

```
⑤ 风控层: 止损7%/止盈20%/移动止损12%/最长20天持仓
④ 趋势逆转: GS方向突变先于其他信号判决
③ 冷静期: 卖出后3天禁止买入
② 综合打分: 7分制双向打分
① 三维信号解析: GS趋势+主力雷达+AI活跃度
```

当前计分表（买入/卖出各满分7分）：

| 条件 | 买入加分 | 卖出加分 | 来源 |
|------|---------|---------|------|
| GS趋势方向正确 | +3 | +3 | GS |
| GS G/S点触发 | +3 | +3 | GS |
| GS tcy/tkc强势 | +1 | +1 | GS |
| 雷达买入/卖出信号 | +2 | +2 | 主力雷达 |
| AI活跃度≥3 | +1 | — | AI |
| AI活跃度≥6 | +1 | — | AI |

#### v4 多票组合策略（`backtest_v4.py`, ~550行）— **当前主力**\n\n精简策略，GS + 主力雷达双指标，多票组合管理，经过6轮迭代。\n\n**2026-06-29 修复（三方评审后）：**

详见 `references/v4_bugfixes_20260629.md`。

**2026-06-30 可视化报告模块：**

- **`backtest_report.py`** — 纯 Python + SVG 报告生成器，**零额外依赖**
  - 运行: `python backtest_v4.py --report`
  - 生成 6 张深色主题图表: 收益曲线(vs 沪深300), 回撤曲线, 月度热力图, 年度汇总, 盈亏分布, 单票拆解
  - 输出: `results/backtest_report_{timestamp}.html`，可离线打开
  - 基准对比自动从 `index_daily` 表加载沪深300数据
  - 不中断回测流程，SVG 渲染无需额外安装
- **`--report` 参数**: `backtest_v4.py` 已新增\n- **主力线信号**：从 `EMA(net_mf_amt, 3) > 0` 修复为**主力线上穿零轴**（`zhuli[i-1] <= 0 and zhuli[i] > 0`）\n- **仓位分配**：从 `cash/3`（第一支吃满，后两支越来越少）修复为固定`position_capital = initial_capital × position_frac`，每只独立\n- **卖出条件**：从"连降2日"修复为**连降3日**（避免频繁震荡出场）。注意：连降天数参数极其敏感（2→4使收益率从+9%跳到+230%），必须逐个参数调。\n- **GS字段**：接收入库已有的 `gs_bull_market`/`gs_g_point`/`radar_zhuli`/`radar_sanhu` 列\n\n**当前参数（`config.V4_PARAMS`）**：\n- **买入**：GS在G区间 AND 主力线上穿零轴 → 次日开盘买入\n- **卖出**（任一触发）：-8%硬止损 / 主力线连降3日 / 利润峰值回调5%\n- **豁免**：盈利>10%持股不卖，利润从峰值回调5%才卖\n- **组合**：最多3只，每只1/3仓位，按主力线上涨幅度排序，卖出后10天冷静期\n\n⚠️ **调参铁律**：参数敏感性极高，必须逐个参数单独回测对比，不要批量改动。连降天数从2→3→4，收益率从+9%→跳过→+230%。每次只改一个参数。

### 4. 回测层 — bridge.py 管线

**bridge.py** 是统一入口。三种使用方式：

```bash
# CLI 运行 v4 多票组合回测
.venv/bin/python bridge.py --engine v4 --codes 301338 000988 301526 000999

# CLI 运行 v3 单票回测
.venv/bin/python bridge.py --engine v3 --codes 000988

# 同步自选股到 Web UI
.venv/bin/python bridge.py --sync-watchlist

# 查看回测历史
.venv/bin/python bridge.py --history
```

**Python API 调用**（在脚本/notebook中使用）：
```python
from bridge import run_v4_pipeline, run_v3_pipeline, load_stock_data

# v4 多票组合 — codes 是 dict{code: name}，参数用 start_date（不是 start）
result = run_v4_pipeline(
    codes={'000988': '华工科技', '301338': '凯格精机'},
    start_date='20250101',          # YYYYMMDD
    initial_capital=1_000_000,
    max_positions=3,
    position_frac=0.333
)

# v3 单票
result = run_v3_pipeline(codes={'000988': '华工科技'}, start_date='20250101')

# 只加载数据不跑回测
df = load_stock_data('000988', start='2025-01-01')
```

⚠️ **常见错误**：`run_v4_pipeline()` 参数名是 `start_date`／`codes`(dict)，不是 `start`／`codes`(list)。

**结果字典字段**（`run_multi_backtest()` 返回）：
- `total_return`, `annual_return`, `max_drawdown`, `sharpe`, `win_rate`, `profit_factor`
- `total_buys`, `total_sells`, `num_trades`, `final_equity`, `n_days`
- **`dates`** — 回测期间每日日期列表 `["YYYY-MM-DD", ...]`，用于基准对齐
- `equity_curve` — np.array 每日权益
- `trades` — Trade 对象列表
- `per_stock` — 各股票累计盈亏

**API 端点**（FastAPI, `app/main.py`）：
- `POST /api/backtest/v4/run` — 执行 v4 多票组合回测
- `GET /api/backtest/v4/config` — 获取策略参数和自选股
- `POST /api/backtest/v3/run` — 执行 v3 单票回测

结果保存到 `v4_backtest_results` 表。

**回测引擎设计原则**：
- 策略只输出信号（盘后），回测引擎管理 entry_price/stop_loss/take_profit
- 交易日信号次日开盘执行
- 止损/止盈以实际入场价为基准
- v4 回测用 `run_multi_backtest()`（从 bridge.py 调用），不接受 backtrader 包装

#### ⚠️ 夏普比率计算陷阱

频繁空仓的策略，空仓期 daily_ret=0。正确做法：从 equity_curve 反算日收益率：

```python
eq_safe = np.where(np.isnan(equity_curve), initial_capital, equity_curve)
daily_returns = np.diff(eq_safe) / np.maximum(eq_safe[:-1], 1)
daily_returns = np.append([0], daily_returns)
dr = daily_returns[1:]
mean_dr = np.mean(dr)
std_dr = max(np.std(dr), 0.001)
excess_daily = mean_dr - 0.02 / 245
sharpe = np.sqrt(245) * excess_daily / std_dr
```

关键：`std` 地板值用 `0.001`（不是 `1e-10`）。

## 数据库

`stock_data.db`（SQLite, 2.2GB, 20+ 表）：

| 表 | 行数 | 说明 |
|----|------|------|
| `daily_kline` | **2,632,072** | 前复权日K线，5,874只, 2019~今。<br>📌 **双重stock_code格式**：① InnerCode格式('605')=全市场5,510只, 日期='YYYY-MM-DD' ✅ **主流** ② 6位SecuCode格式('000988')≈147只watchlist, 日期='YYYYMMDD' ⚠️ 子集<br>⚠️ **InnerCode批次 amount=0**：最新2个交易日 amount 列=0，需 `close×volume` 回退后方可传给 calc_zhuli_holdings |
| `moneyflow_daily` | **14,232,762** | 🆕 **同花顺 THS 全量资金流向**（5,663只, 2007~今），四档买卖量+额 |
| `hk_hold` | 2,975,430 | 🆕 **沪深港通持股**（3,008只, 2014~今） |
| `cyq_chips` | 12,134,465 | 🆕 **每日筹码分布**（5,195只, 2018~今），各价位占比 |
| `cyq_perf` | 6,434,723 | 🆕 **筹码成本+胜率**（分位成本, 均价, 胜率） |
| `ind_moneyflow` | 5,569,924 | 🆕 **行业板块资金流向**（1,041板块, 2011~今） |
| `index_daily` | ~4,500 | 🆕 **沪深300指数日线**（000300.SH, 2005~今，Tushare） |
| `dz_dailyquote` | 1,325,194 | 恒生聚源日线（不复权） |
| `adj_factors` | ~6,000 | 复权因子 |
| `minute_kline` | 243,435 | 1分钟线 |
| `minute5_kline` | 58,176 | 5分钟线 |
| `v4_backtest_results` | — | v4回测结果 |
| `watchlist` | 148 | 自选股 |
| 其他 | — | 股本/股东/ROE/营收 |

**moneyflow_daily 资金流管线（2026-06-29 更新）**：
- **数据源已切换为同花顺 THS 全量数据**，不再使用东方财富或问财 API
- 覆盖 5,663 只 A 股，2007-01-04 ~ 2026-06-26，14,232,762 行
- 四档（小单/中单/大单/特大单）买入卖出量（手）+ 额（万元），已算好逐行净流入
- 来源：购买的 quant-data/moneyflow/ 目录 CSV 文件全量导入
- `data_source='ths'`，主键 `(stock_code, date)`
- 东方财富存量数据保留为 `data_source='eastmoney'`（31 行），不做主数据源

| moneyflow_daily THS 字段 | 说明 |
|--------------------------|------|
| `buy_sm_vol/sell_sm_vol` | 小单买卖量(手) |
| `buy_md_vol/sell_md_vol` | 中单买卖量(手) |
| `buy_lg_vol/sell_lg_vol` | 大单买卖量(手) |
| `buy_elg_vol/sell_elg_vol` | 特大单买卖量(手) |
| `net_mf_vol` | 总净流入量(手) |
| `buy_sm_amt/sell_sm_amt` | 小单买卖额(万元) |
| `buy_md_amt/sell_md_amt` | 中单买卖额(万元) |
| `buy_lg_amt/sell_lg_amt` | 大单买卖额(万元) |
| `buy_elg_amt/sell_elg_amt` | 特大单买卖额(万元) |
| `main_net_amt` | 主力净额(万元) |
| `net_mf_amt` | 总净流入额(万元) |
| `data_source` | `'ths'` 或 `'eastmoney'` |

- `references/signal_enhancer-integration-testing.md` — 🆕 signal_enhancer 集成验证模式：六项检查、列名不匹配记录、修复工作流（2026-07-05）
- `references/ths-moneyflow-import.md`
- `references/formula-practical-review-methodology.md` — 🆕 同花顺自定义指标实战适用性审查方法论：信号频率分析、买入可操作性、SMA等价验证、RSI辅助改进方案。当用户要求审查一个公式的实战可用性时加载此参考。

### 添加自选股

**数据流**：SQLite 为主数据源，JSON 为自动导出快照。

```
增删自选股 → Web UI / CLI → SQLite (watchlist + wl_groups)
                              → _wl_export_db_to_json()
                                → watchlist.json (给人看 + Git diff)
```

1. `config.py` → `STOCKS_V4` dict 新增 `"代码": "名称"`
2. `bridge.py --sync-watchlist` → 同时写 SQLite + JSON（`_sync_watchlist_to_db()`）
3. 下次 Coze 增量更新（01:05 cron）时，`dz_dailyquote` 已自动包含该股数据，无需额外拉取
4. 更新 Hermes memory 中的自选股列表

**SQLite 表结构**：

```sql
-- 分组元数据
wl_groups (group_id TEXT PK, group_name TEXT, created_at TEXT)

-- 自选股（支持多分组）
watchlist (stock_code TEXT, group_id TEXT, stock_name TEXT, group_name TEXT, added_at TEXT,
           PRIMARY KEY (stock_code, group_id))
```

**常用 SQL**：
```sql
-- 查默认自选股
SELECT stock_code, stock_name FROM watchlist WHERE group_id = 'default';

-- 自选股 + 最新K线 JOIN
SELECT w.stock_code, w.stock_name, k.close
FROM watchlist w LEFT JOIN daily_kline k ON w.stock_code = k.stock_code
WHERE w.group_id = 'default' AND k.date = (SELECT MAX(date) FROM daily_kline WHERE stock_code = w.stock_code);
```

**核心函数**（`app/main.py`）：
- `_wl_db_add_stock()` / `_wl_db_remove_stock()` — 增删股票，自动导出 JSON
- `_wl_db_add_group()` / `_wl_db_rename_group()` / `_wl_db_delete_group()` — 分组管理
- `_wl_export_db_to_json()` — SQLite → JSON 双向桥，每次写操作后自动调用

无需手动 `fetch_daily_kline` — cron job 自动处理。

## 每日晨报结构

三板块精简格式（2026-06-27 起），只展示数据质量：

```
▎📈 日线数据
  最新日期 | 覆盖股票数 | 总行数
  自选涨跌: 总数 涨N 跌N 平N
  🔼/🔽 TOP3 涨跌幅

▎💰 资金流向
  最新日期 | 覆盖数 | 总行数 | 来源分布
  成交量/成交额: ✅/⚠️/❌
  主力净流入 TOP5 (代码 + 名称 + 金额)

▎⚙️ 系统运维
  venv / 日报 / qfq导入 / 资金流向回补 一行状态
```

脚本：`~/my_quant_system/scripts/daily_morning_report.sh`

## 注意

- 问财资金流向回补 cron 已停用（`0 4 * * *` 已删除）— THS 全量数据覆盖更全
- `daily_moneyflow_iwencai.py` 已保留但不维护
- 沪深300已入库至 `index_daily` 表，可通过 Tushare MCP 增量更新

## 已知问题\n\n1. **恒生聚源仅覆盖1年**（2025-06-23起）— 更早回测需走 `daily_kline` fallback\n2. **adj_factors 未全覆盖** — Tushare API 频率限制（1次/小时），目前仅 000988 有完整复权因子。但**这不影响回测准确性**：因为 `daily_kline`（主 fallback 路径）的数据已经是 Coze 前复权，不需要 adj_factors。警告仅来自 `dz_dailyquote` 路径。\n3. **沪深300基准数据源** — 通过东方财富免费 API（push2his.eastmoney.com）拉取，不要依赖 Tushare index_daily（限频 1次/小时）。脚本：`scripts/import_hs300_v2.py`。注意 `index_daily` 表的 pct_chg 字段当前全为 NULL（旧导入管线遗漏），基准 curve 对齐应使用 `close` 计算日收益率，不能依赖 pct_chg 字段。\n3. **v4 主力线连降参数敏感** — 连降天数2→4使收益率从+9%跳到+230%，必须逐个参数调\n4. **venv 是 Python 3.9**（不是 3.11）\n5. **Git push 代理** — 国内 GitHub 直连可能超时\n6. ~~moneyflow_daily 增量更新由 cron 每日 18:30 自动执行~~ → **已废弃**。THS 全量数据已一次性导入，后续增量方案待确认。`scripts/process_moneyflow.sh` 和 `coze_incremental_update.py` 已停用。\n7. **THS 资金流最新日期=2026-06-26**（已停更），而 Tushare DC 每日增量但只有净额。如需近期暗盘/持仓数据需额外处理。\n8. **backtest_v4 混合回测失真**（✅ 已修复 2026-07-02：merge 后打印因子覆盖率 %，<50% 警告；回填完成前分阶段输出）。
    **覆盖率日志在筛选中的缺失**：backtest_v4.py 有覆盖率输出（`因子覆盖率: X% (Y/Z 天)` + `因子覆盖区间: X/Y 天`），但 `screen_v4.py` 的因子表模式无覆盖率报告——它假设因子表完整。建议 track: 在 `screen_v4.py` 增加每日 factor_count 行数与理论值对比。
9. **每日成交额限额**：`moneyflow_daily.THIS 的成交量列和成交额列有 0 值问题 — 11,152 只 Tushare DC 数据只有净额，**不含**分档买卖金额，不可用于暗盘资金/主力持仓计算，仅 OHLCV 指标可用。
10. **`except: continue` 静默吞错**（2026-07-02 教训）：screen_v4.py 最初用裸 `except: continue`，导致所有失败股票零输出且无痕迹。必须加 logging 或异常计数器。
11. **ST/*ST/退市排除**（已修复 2026-07-02 → 2026-07-03 增强）：screen_v4.py 现通过 `filter_st_stocks()` 在打印和保存前过滤 ST 股。6/26 实测：5,206 只中 215 只 ST 被移除，4条件命中从 24→23 只。  
    **⚠️ 三处 ST 检测未统一：**
    - `screen_v4.py` `is_st_stock()` — 只检 `'ST' in name`  
    - `backtest_v4.py` `is_stock_st()` — 只检 `'ST' in name`  
    - `screen_monthly_validation.py` — 同时检 `'ST' in name or '退' in name`  
    **建议统一为**：`'ST' in (name or '').upper() or '退' in (name or '')`，并考虑从 `tushare.stock_st` 接口获取正式 ST 列表做补充。  
    **回测测同样需要双重保护**：`is_stock_st()` + `is_stock_suspended()`（检查 volume=0 AND close≈pre_close）。
12. **cron 时序冲突 — 因子管线在资金流之前运行**（✅ 已修复 2026-07-02：因子更新改为 0 19 运行，在资金流 18:45 之后）。
13. **backtest_v4 参数硬编码**（2026-07-02 评审发现）：generate_signals() 中连降天数（3日）和止损比例（-8%）硬编码在函数体内，不从 config.V4_PARAMS 读取。config 改了但代码不跟随。修复：函数接受参数，默认值与 config 一致。

14. **4条件信号密度过高**（2026-07-03 审查发现）：2026-06-26 因子表模式下 23 只股票满足全部 4 条件，远超 `backtest_v4.py` 的 `max_positions=3` 上限。23 只需排序后取前 3，意味着大量信号无法执行。建议增加二级筛选：成交额>2亿、振幅>3%、暗盘资金强度排序。当前排序仅基于主力线上涨幅度（绝对值），未考虑暗盘资金趋势。

16. **⚠️ daily_factors merge 日期格式静默失败**（2026-07-05 审查发现）：`backtest_v4.py` 中 `generate_signals()` 的 factor 加载（L761-797）用 `df.merge(f_df, on='date', how='left')` 合并 daily_factors 数据。但：
    - `daily_factors.trade_date` 存储格式为 `YYYY-MM-DD`（如 `'2026-06-26'`）
    - `daily_kline.date` 对 SecuCode 股票（watchlist 约 147 只）使用 `YYYYMMDD`（如 `'20260626'`）
    - 精确字符串比较导致 **~90% 行 merge 失败**，factor 列全部 NaN → 被默认值覆盖（zhuli_holding=100.0, dark_pool_inflow=1）
    - Enhanced 模式下，这使 `holding_ok` 和 `inflow_ok` 永远为 True，买入评分虚高 +4 分
    - **覆盖率日志仍会显示低百分比**（如 10.6%），但用户可能误判为"部分覆盖尚可接受"
    - **SQLite 实测**（code='000988'）：daily_kline 132 行中仅 14 行 exact match（10.6%），去掉横线后 141 行匹配（≈全部）
    - 修复：merge 前统一日期格式 `f_df['date'] = f_df['date'].str.replace('-', '')` 或 `df['date'] = df['date'].str.replace(r'(\d{4})(\d{2})(\d{2})', r'\1-\2-\3', regex=True)`
    - 同样问题存在于 `screen_v4.py` 的因子表查询中 — 查询参数必须与 `daily_factors.trade_date` 格式一致

17. **signal_enhancer 评分权重与 IC 实证不符**（2026-07-05 审查发现）：
    - IC 报告（fwd_1d, 2026-05-29~2026-06-25）显示：涨停首封时间分段 IC=0.1044，GS牛市信号 IC=0.0720，主力线上穿 IC=0.0189
    - 但当前评分中，三者权重相同（均为 3 分），不反映 IC 差异
    - `enhanced_buy_decision` 的 "FULL"(≥15) vs "BUY"(≥10) 在回测引擎中无实际区分——`sig_buy` 只检查 score≥10，FULL 信号被降级为普通买入且排序上无区别
    - `buy_rank[i] = float(score)` 使用离散整数评分排序，导致平局（当 market_verify 表不存在时，4条件全满足的股票全部得 10 分）
    - 建议：权重改为 IC 归一化比例，FULL 信号应反映在仓位分配上

15. **IC 分析器 JOIN 覆盖率已修复**（✅ 2026-07-02 修复）：`ic_analyzer._load_kline()` 直接从 `daily_kline` 读 stock_code，但 `daily_kline` 大部分数据用 InnerCode（`10000`、`10017` 等），而 `daily_factors` 用 6位 SecuCode。JOIN 时编码不匹配，导致：
    - 2024 年 135 天：5,033 只股票 → 仅 16 只匹配（0.3%）
    - 2026 年有效截面仅 3 天（2026-06-24/25/26），~142 只（来自 8 位日期格式的 watchlist 数据）
    - IC 报告中"可用的有效截面"长期 < 10 只，所有因子 IC 显示 NaN
    - **修复**: 给 `_load_kline()` 加 InnerCode→SecuCode 映射（复用 `batch_load_data()` 中已有的 `all_ashare_stocks.csv` 映射），预计可让 2024 年 135 天 × 5,000 只股票可用。
    - 详见 [`factor-calculation-engine` 技能](https://hermes-agent.nousresearch.com/docs/skills/factor-calculation-engine) 的 `references/data-coverage-diagnostic-methodology.md`。

18. **⚠️ RSI 公式 `loss.replace(0, np.nan)` 导致连续上涨日 RSI=NaN**（2026-07-06 审查发现）：RSI 实现中 `loss.replace(0, np.nan)` 在窗口内全为上涨（loss=0）时将 RSI 变为 NaN，正确值应为 100。  
    - 601138(工业富联)买入日(2025-07-01)：前6日连阳，RSI6=NaN（应为100）  
    - 600522(中天科技)卖出日(2026-06-25)：连续行情下RSI6=NaN  
    - 直接下游：策略买入条件若依赖RSI阈值，将丢失这一信号触发  
    - 修复方向：去掉 `loss.replace(0, np.nan)`，改用 `loss` 直接参与除，再对 `rs` 处理无穷，loss=0 时 RSI=100

## 亏损诊断流程

当策略在特定股票上亏损时，三步诊断：

1. **检查买入持有收益**：区分是熊股拖累还是策略问题
2. **逐笔交易分析**：买入zhuli值、持仓峰PnL、卖出zhuli值、持有天数
3. **模式识别**：信号簇聚 / 高位接盘 / 卖出太晚

脚本：`analyze_losers.py`（已迁入 `~/my_quant_system/`）。

## 文件参考

- `references/data_pitfalls_20260702.md` — 7个数据陷阱：日期格式不统一/amount=0/MONEY=0/编码映射/列名不匹配/except沉默/CSV迭代器耗尽
- `references/strategy_library_architecture.md` — 🆕 策略武器库架构、添加新指标模板、暗盘资金适配方案
- `references/systems_relationship.md` — 与 daily_stock_analysis 的关系 + SQLiteFetcher 桥接方案
- `references/ths_indicators_guide.md` — 每个指标的逐行公式→Python映射
- `references/v4_gs_zhuli_strategy.md` — v4策略设计文档和迭代历程
- `references/rule_engine_strategy.md` — v3规则引擎完整设计
- `references/tencent_data_api.md` — 腾讯 ifzq API 文档
- `references/unified_system_files.md` — 统一后完整文件清单
- `references/moneyflow_pipeline.md` — 东方财富资金流数据管线
- `references/adj_factor_pipeline.md` — 🆕 复权因子管线：adj_factors 表设计、复权计算逻辑、pull_adj_factors.py 使用
- `references/screening_methodology.md` — 全A股扫描方法、列名陷阱、MONEY修复、THS条件对齐、4条件与backtest条件差异
- `references/factor_engine_design.md` — 🆕 因子计算引擎完整技术方案（982行）
- `references/data_pitfalls_20260702.md` — 🆕 7个数据陷阱：日期格式不统一/amount=0/MONEY=0/编码映射/列名不匹配/except沉默/CSV迭代器耗尽
- `references/multi-round-fix-review-pattern.md` — 🆕 多轮修复-复盘工作模式（2026-07-03 因子工程复盘经验）
- `references/external-tool-evaluation.md` — 🆕 外部量化工具/生态系统评估框架（Quantskills/GitHub对比方法论，2026-07-02）
### ⚠️ MONEY=0 大坑（2026-07-02）

MoneyflowAdapter._map_to_ths_columns() 设置 MONEY=0（THS数据无amount列）。这导致 calc_dark_pool 中 小单买入初=MONEY-大单-特大单-中单=负数，整个暗盘资金公式崩溃。

症状：全A股4条件扫描得0只；同花顺选出的股票暗盘全部不过。

修复：将 daily_kline 的 amount 按日期对齐后填入 mf_mapped：
```python
mf_mapped = adapter._map_to_ths_columns(mf)
amt_map = dict(zip(dk_fixed['date'], dk_fixed['amount']))
mf_mapped['MONEY'] = mf_mapped['date'].map(amt_map).fillna(0).values
dp = calc_dark_pool(dk_fixed, mf_mapped)
```

修复效果：全A股4条件扫描 0只→26只；同花顺匹配率 0/11→10/11。

### ⚠️ CSV DictReader 迭代器耗尽

```python
# ❌ 错误：DictReader 是迭代器，第一次 dict 用完 reader
with open("file.csv") as f:
    reader = csv.DictReader(f)
    dict1 = {r['key']: r['val'] for r in reader}  # reader exhausted here
    dict2 = {r['val2']: r['val3'] for r in reader}  # EMPTY!

# ✅ 正确：先转 list
with open("file.csv") as f:
    rows = list(csv.DictReader(f))
dict1 = {r['key']: r['val'] for r in rows}
dict2 = {r['val2']: r['val3'] for r in rows}
```

这是 2026-07-02 的教训。screen_v4.py 和 debug 脚本因此一直使用空白的 secu_to_name/secu_to_inner 字典，导致所有扫描结果股票名称为空、月度验证11只股票无法找到 InnerCode。

## 🧩 因子工程（2026-07-02 设计阶段）

将独立指标预计算入 daily_factors 表，实现"一次计算，多次使用"。

### 架构

```
daily_kline ──┐
              ├─→ Factor Pipeline → daily_factors → screen_v4 (查表)
moneyflow ────┘                    (预计算)       → backtest_v4 (复用)
```

### 已有产物

| 文件 | 位置 | 说明 |
|------|------|------|
| `factor_pipeline.py` | `~/my_quant_system/factor_engine/` | 因子管线代码（含CLI，已 `-t init` 验证） |
| `factor_ddl.sql` | 同上 | 5张表DDL |
| `README.md` | 同上 | 完整技术方案文档 |
| `docs/factor_engine_design.md` | `~/my_quant_system/docs/` | 计算引擎技术方案（982行） |
| `docs/factor_engineering_architecture.md` | `~/my_quant_system/docs/` | 代码架构方案（759行） |

### 表结构要点

| `factor_ddl.sql` | 同上 | 5张表DDL |
| `README.md` | 同上 | 完整技术方案文档 |
| `docs/factor_engine_design.md` | `~/my_quant_system/docs/` | 计算引擎技术方案（982行） |
| `docs/factor_engineering_architecture.md` | `~/my_quant_system/docs/` | 代码架构方案（759行） |
| **`strategy_library/factors.py`** | 系统内 | 🆕 因子表管理模块（6函数），调用真实 indicators。已验证 5,206只×3日=15,618行，0失败 ✅ |
| **`scripts/import_daily_factors.py`** | 系统内 | 🆕 CLI入口（4命令：init/daily/backfill/validate）。已验证 daily 命令 ✅ |

### 关键函数签名

```python
def ensure_schema(db_path) -> None                        # 建表（执行 factor_ddl.sql）
def batch_load_data(db_path, start, end) -> dict           # 2次SQL批量加载5,206只×120天K线+60天资金流
def compute_factors(code, kline_df, mf_df) -> dict         # 调用5个真实indicators，返回15个因子
def batch_compute_and_write(stock_data, target_date, db)   # 批计算+upsert（500行/批）
def query_factors(db, date, conditions=None) -> DataFrame  # 带条件查表
def get_factor_history(db, code, start, end) -> DataFrame  # 按股票查时间序列
```

### 部署状态

| 阶段 | 内容 | 状态 |
|------|------|------|
| P0 基础设施 | factors.py + config适配 | ✅ **完成** |
| P1 全量回填 | 历史2年因子数据批量计算 | ⏳ **进行中**（cron: backfill_cron.sh, 断点续传） |
| P2 消费者改造 | screen_v4查表 + backtest_v4买入4条件对齐 | ✅ **完成** |
| P3 上线监控 | cron（`每日因子更新` 工作日19:00）+ 每日增量 | ✅ **已部署**（⚠️ 必须19:00后运行，等资金流管线18:45更新完毕） |

### screen_v4.py 重构（2026-07-02）

`screen_v4.py` 改为**双模式**：

```bash
# 模式1：因子表查询（毫秒级）
python screen_v4.py --date 2026-06-25

# 模式2：回退逐只计算（因子表无数据时自动触发，或强制）
python screen_v4.py --date 2026-06-25 --fallback
```

`--date` 参数支持任意日期。因子表有数据时查表 <1秒，无数据时fallback到旧逐只计算模式（~10分钟）。

已验证：因子表2026-06-25给出44只4条件命中（手动逐只43只，1只差异来自MONEY对齐逻辑），2026-06-26给出24只（旧手动因日期格式bug只扫147只→0只，现扫5,206只→24只）✅

### Hermes Cron（2026-07-02 新增）

| Job | schedule | script | no_agent | 用途 |
|-----|----------|--------|----------|------|
| 每日因子更新 | `0 19 * * 1-5` | `daily_factor_update.sh` | ✅ | 收盘后计算当日因子，推入 daily_factors（19:00 资金流已有） |
| 因子回填-历史全量 | 一次性 (08:05) | `backfill_cron.sh` | ✅ | 回填2024-06-04→2026-06-23，逐日+断点续传 |

> ⚠️ cron no_agent 脚本必须放在 `~/.hermes/scripts/` 目录下，且用 `chmod +x` 确保可执行。脚本中失败时必须在 stdout 打印 `FACTOR_UPDATE_FAILED` 标记（cron本地日志可查）。
> ⚠️ cron no_agent 脚本修改后，需同时同步 `.hermes/scripts/` 和 `my_quant_system/scripts/` 两份副本。cron实际执行的是 `.hermes/` 版本。

- stock_code统一用6位SecuCode（映射自all_ashare_stocks.csv）
- 主力持仓递推需拉120天历史窗口，不能只取当天
- 每日新增约5,200行，batch upsert 500行/批
- 首次回填按月分批
- 保留fallback：查表为空时自动回退逐只计算

## 🔧 信号增强模块（financial_api/signal_enhancer.py）

从 `backtest_v4.py` 的 `generate_signals()` 分离出一层可插拔的信号增强逻辑。

### 文件位置

```
~/my_quant_system/
├── financial_api/
│   ├── __init__.py
│   └── signal_enhancer.py        ← 🆕 信号增强评分模块
└── backtest_v4.py                ← 原引擎（不修改）
```

### 设计原则

1. **纯函数，不持有状态** — 所有输入通过参数传入，返回 (score, detail) tuple
2. **数据可选，优雅降级** — 新表 (`limit_up_pool`/`limit_up_ladder`/`dragon_tiger_daily`/`hot_stock_daily`) 不存在时返回默认值，不阻塞主流程
3. **与引擎解耦** — 不修改 `backtest_v4.py` 一行代码；外部通过 `build_base_signal()` 桥接

### 三个核心函数

| 函数 | 用途 | 返回 |
|------|------|------|
| `enhance_buy_signal(base_signal, conn, trade_date, stock_code)` | 综合评分买信号 | `(0-20分, detail_dict)` |
| `enhance_sell_signal(position_info, conn, trade_date, stock_code)` | 三级卖出检查表 | `(A/B/C/NONE, 原因文本)` |
| `dynamic_max_positions(conn, trade_date)` | 连板情绪动态仓位 | `int (1~3)` |
| `build_base_signal(...)` | 桥接 — 从主引擎的中间变量构造 base_signal | `dict` |
| `enhance_all_signals(...)` | 一站式集成入口（自动打开/关闭 conn） | `dict` |

### 买入评分规则（max=20）

```
Base Score (max=10)
  GS信号 (2) + 主力线上穿 (3) + 主力持仓>20% (2) + 暗盘连2日流入 (2)

Market Verify (max=10) — 查新表，无数据时=0
  涨停封板强度 (0-3) — open_times=0→3分, 1→2分, >1→1分
  龙虎榜净买入 (0-3) — >5千万→3, >1千万→2, >0→1
  热榜排名 (0-1)     — rank≤50→1, ≤150→0.5, ≤300→0.5, >300→0
  连板情绪 (0-2)     — 2板以上占比>30%→2, >20%→1.5, >10%→1

决策阈值: ≥15→FULL(满仓), ≥10→BUY, <10→NONE
```

### 三级卖出检查表（优先级 A > B > C）

```
A_强制卖出 (-8%止损 / 主力3连降 / 连板断板 / 龙虎榜净卖>买入50%)
B_建议卖出 (峰值回调>5% / 热榜3日降 / 打压异动 / 主力线动能减弱)
C_减半仓   (GS转空 / 暗盘转流出 / 游资对倒)
```

### 新增数据库表

⚠️ **这些表由 Financial-API 管线创建，列名与实际 Tushare/同花顺返回一致。编写 SQL 前必须 `PRAGMA table_info` 验证！** 详见 `references/signal_enhancer-integration-testing.md`。

| 表 | 来源 | 关键字段 |
|----|------|---------|
| `limit_up_pool` | Tushare limit_list / 通达信 | `trade_date, thscode, open_times, first_limit_time, last_limit_time` |
| `limit_up_ladder` | Tushare limit_step | `trade_date, board_nums, stock_count, stock_list` |
| `dragon_tiger_daily` | Tushare top_list | `trade_date, thscode, buy_top_amount, sell_top_amount, net_amount` |
| `hot_stock_daily` | Tushare ths_hot / dc_hot | `trade_date, thscode, rank, pct_change` |
| `cls_stock_shock` | Tushare cls_stock_shock | `trade_date, thscode, type, reason` |

### 自测

```bash
cd ~/my_quant_system && python3 financial_api/signal_enhancer.py
```

模块自带 8 个自测用例，覆盖：全条件评分、部分条件、A/B/C 三级卖出、默认仓位、桥接函数。不依赖外部数据库。

### 集成验证（修改信号增强后必须做）

修改 `signal_enhancer.py` 或 `backtest_v4.py` 的增强集成后，不要直接跑全量回测——先跑 `test_enhanced.py` 做六项检查：

```bash
cd ~/my_quant_system
~/.pyenv/versions/3.11.11/bin/python3 test_enhanced.py
```

| # | 检查 | 验证内容 | 常见失败 |
|---|------|---------|---------|
| 1 | 模块导入 | 3核心函数加载 | sys.path / import 路径 |
| 2 | DB 表结构 | 4张增强表的列名、行数 | **SQL 列名 vs 实际列名不匹配** |
| 3 | 语法检查 | backtest_v4 + signal_enhancer | patch 后的缩进损坏 |
| 4 | 功能测试 | 模拟 dict 调用 3 函数 | 参数签名（dict vs 平铺） |
| 5 | CLI 帮助 | `--enhanced --help` | argparse 冲突 |
| 6 | 端到端 | 单股 `--enhanced --codes 000899` | SQL 运行时错误 |

**列名不匹配是 #1 失败源**。`limit_up_pool` 用 `first_limit_time`（不是 `first_time`），`limit_up_ladder` 用 `board_nums`（不是 `nums`）。不相信直觉，只看 PRAGMA。完整模式见 `references/signal_enhancer-integration-testing.md`。

### ⚠️ 已知局限（2026-07-05 审查）

1. **评分权重已按 IC 校准**（2026-07-05 修复）：涨停因子权重（limit_up_strength=3）> GS信号权重（gs_signal=2）。hot_rank_score IC=0.023 降为 1 分。详见 `references/enhanced-buy-logic-review-20260705.md`。
2. **"FULL" 信号语义丢失**：≥15 分返回 "FULL"，但回测引擎只检查 `score >= 10`，FULL 和 BUY 无仓位差异。`buy_rank` 排序也使用相同 score 值，不区分 FULL。
3. **排序平局问题**：enhanced 模式用 `float(score)`（离散整数 0-20）排序，原逻辑用 `zhuli[i]-zhuli[i-1]`（连续值）。market 表不存在时 4条件全满足的股票全部得 10 分 → 排序不可复现。
4. **backtest_v4.py 中 daily_factors 的 date 列格式为 YYYY-MM-DD，但 daily_kline 的 date 列对 SecuCode 股票为 YYYYMMDD**，merge 时精确字符串匹配导致 ~90% 行匹配失败（详见已知问题 #16）。

### ⚠️ Import 模式陷阱（2026-07-05 修复）

原版代码在 `generate_signals()` 和 `run_multi_backtest()` 主循环中分别做 `sys.path.insert` + `from signal_enhancer import ...`，每函数/每交易日重复执行。

**正确做法：顶层级单次 import + `_enhancer.xxx()` 调用**

```python
# ✅ 在 backtest_v4.py 顶部：一次导入，全局使用
try:
    import signal_enhancer as _enhancer
except ImportError:
    _enhancer = None

# ✅ 所有调用点使用 _enhancer.xxx() + guard
if use_enhanced and _enhancer is not None and conn is not None:
    base_signal = _enhancer.build_base_signal(...)
    score, detail = _enhancer.enhance_buy_signal(...)
    sell_level, reason = _enhancer.enhance_sell_signal(...)
    max_pos = _enhancer.dynamic_max_positions(...)
```

### 集成到 backtest_v4.py 的示例

```python
# 在文件顶部（不是函数内部）导入
try:
    import signal_enhancer as _enhancer
except ImportError:
    _enhancer = None

# 在 generate_signals() 或 run_multi_backtest() 内部使用
if _enhancer is not None:
    bs = _enhancer.build_base_signal(
        zhuli=zhuli[i], zhuli_prev=zhuli[i-1],
        zhuli_holding=zhuli_holding[i],
        dark_pool_inflow=dark_pool_inflow[i],
        prev_inflow=prev_inflow[i],
        gs_bull_market=gs_bull[i], gs_g_point=gs_g[i],
    )
    buy_score, detail = _enhancer.enhance_buy_signal(bs, conn, date_str, code)
    sell_level, reason = _enhancer.enhance_sell_signal(pos_info, conn, date_str, code)
    max_pos = _enhancer.dynamic_max_positions(conn, date_str)
```

## 🗺️ 全A股条件筛选

新增方法（2026-07-01）：从 ~5,500 只全 A 股中扫描满足 N 个条件的股票，输出候选池表。
2026-07-02 扩展：多日遍历扫描+信号后+5/+10/+20日表现追踪。

### 方法

```python
cur = db.execute("SELECT DISTINCT stock_code FROM daily_kline WHERE date='2026-06-26'")
inner_to_secu = {r['InnerCode']: r['SecuCode'] for r in all_ashare_stocks}
for inner in all_codes:
    secu = inner_to_secu.get(inner, '')
    dk = pd.read_sql_query("...WHERE stock_code=?", params=(inner,))
    mf = pd.read_sql_query("...WHERE stock_code=?", params=(secu,))
    mf_mapped = adapter._map_to_ths_columns(mf)
    gs = calc_gs_signal(dk); rd = calc_zhuli_radar(dk)
    dp = calc_dark_pool(dk, mf_mapped); zh = calc_zhuli_holdings(dk, mf_mapped)
```

### ⚠️ 陷阱\n\n0. **ST/*ST/退市必须排除** — 所有全A股筛选脚本必须在 name_map 层加 `'ST' in name.upper()` 过滤，并要求停牌检测。\n1. daily_kline 日期格式混用：`'20260626'`(无横线) 仅 147 只；`'2026-06-26'`(有横线) 5,510 只。修复：SQL 中用 REPLACE 统一为无横线格式比较。\n2. moneyflow_daily 用 SecuCode，only InnerCode。需 all_ashare_stocks.csv 做双向映射。映射失败 fallback：6位 SecuCode 直接假设。\n3. 指标列名不匹配：zhuli_holding(单数) ≠ zhuli_holdings；暗盘净额=dark_pool_1d；流入信号=dark_pool_inflow_signal。\n4. ~5,500 只全量扫描约 7-10 分钟。\n5. **禁止裸 `except: continue`** — 脚本若静默吞错，所有失败股票零输出且无痕迹。必须加 logging.warning 或异常计数器。\n6. daily_kline InnerCode 批次的 `amount` 在最新2个交易日=0，传给 `calc_zhuli_holdings` 前必须 `close×volume` 回退，否则 DDX 除零→天文数字→持仓钳制到 2.08%。

## 扩展生态

### 问财 Skill Hub（OpenClaw 技能）

CLI 已安装：`~/.iwencai-skillhub/`，命令 `iwencai-skillhub-cli`。已安装技能：

| 技能 | 用途 |
|------|------|
| 估值模型方法论 | DCF/DDM/SOTP/PE-Band/PB-ROE/EV-EBITDA 估值框架 |
| 基本面因子筛选 | PE/PB/ROE 价值/成长股票筛选 |
| 市场情绪分析 | 恐贪指数/PCR/融资融券/北向资金/社交舆情 |
| 财务报表深度解读 | 三表勾稽/盈利质量/12项造假红旗/杜邦分析 |
| 因子研究框架 | IC/IR分析/分层回测/因子组合 |
| 盈利预期修正分析 | SUE/PEAD/管理层指引/盈利质量评分 |
| 盈利预测与一致预期分析 | Top-Down/Bottom-Up预测/SUE/A股财报日历 |
| 分钟级数据分析 | Tushare/OKX/yfinance 分钟K线 + VWAP/TWAP |

安装新技能：`iwencai-skillhub-cli --dir ~/.iwencai-skillhub/skills install "技能名"`

### Hermes 原生技能

| 技能 | 位置 | 用途 |
|------|------|------|
| `a-share-valuation` | `~/.hermes/skills/research/a-share-valuation/` | A股估值分析框架（翻译自问财估值模型方法论） |
| `a-share-research` | `~/.hermes/skills/research/a-share-research/` | 机构研报收集（Tushare MCP + 问财） |
