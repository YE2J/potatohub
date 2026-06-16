---
name: a-share-quant-backtest
description: "A股量化回测与策略开发：数据获取 → 指标计算 → 策略引擎 → 回测评估。统一架构于 ~/my_quant_system/，覆盖同花顺/通达信公式的严格Python翻译、SQLite+Parquet数据层、规则引擎策略设计。"
version: 2.0.0
author: Hermes Agent
tags: [a-share, backtest, quantitative, strategy, tonghuashin, tdx]
---

# A股量化回测与策略开发

## 触发条件

当用户提到：量化回测、写策略、回测指标、python回测、指标评估、信号生成、策略引擎、backtest、v4回测、GS信号、主力雷达 等。

## 用户偏好

- **公式翻译必须严格保留原逻辑** — 通达信/同花顺的公式语言（SMA公式参数、CROSS语义、AND/OR优先级）必须逐行精确复现，不允许"简化"或"优化"原版计算。
- 数据源优先使用已验证可用的 — 腾讯 ifzq 历史K线API优先，akshare 作为后备。数据统一存储在 SQLite `stock_data.db`。
- 暗盘资金和主力持仓指标**代码已存在于 strategy_library**，标记为 `available`/`degraded` — 有 Tushare 数据时可激活，不可得时降级运行。
- **所有工作基于统一系统 `~/my_quant_system/`** — 旧系统已删除，不要再引用。
- **所有导入使用 `strategy_library.indicators`** — `indicators_tdx.py` 是向后兼容 wrapper，新代码不要直接从它导入。

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
├── backtest_v4.py                          ← v4 多票组合引擎（导入已适配）
├── bridge.py                               ← 桥接：DB→指标→回测→DB保存
├── analyze_losers.py                       ← 亏损诊断
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

### 1. 数据层

- **SQLite `stock_data.db`**（53MB）：307只股票，44K日线 + 243K分钟线 + 58K 5分钟线，14张表（含 v4_backtest_results）
- **Parquet 缓存** `data/parquet/`（106文件，860KB）
- **每日自动更新**：
  - K线数据：cron `fda7975b8524`，通过 shell wrapper `daily_update_v2.sh` 每夜 00:00 从腾讯 API 拉取
  - 资金流数据：cron `209c43908019`，每日 18:30（收盘后）通过 Hermes `web_extract` 从东方财富 API 拉取全部 STOCKS_V4 99只自选股，增量写入 `moneyflow_daily`。lmt=3 只取最新3日，每批4只股票。
- ⚠️ **Cron Python 陷阱**：cron 运行 `.py` 脚本时不保证使用项目 venv。必须用 **shell wrapper** 显式指定：`exec "$HOME/my_quant_system/.venv/bin/python" "$HOME/.hermes/scripts/daily_update.py"`。直接用 `.py` 会因系统 Python 缺少 pandas/numpy 报 `ModuleNotFoundError`。
  - Wrapper 脚本：`~/.hermes/scripts/daily_update_v2.sh`
  - Cron job `fda7975b8524` 已配置 `deliver=origin`，成功/失败都会推送到微信
- **`StockDataManager.load_to_dataframe(code, start, end)`**：优先从 SQLite 读取，回退 Parquet。返回标准 OHLCV DataFrame。这是 bridge.py 和 backtest_v4.py 的数据入口。

腾讯 ifzq API:
```
http://ifzq.gtimg.cn/appstock/app/fqkline/get?param={market}{code},day,{start},{end},{max_records},qfq
```
- `market`: sz=深市(0/3开头), sh=沪市(6开头)
- 单次最多 ~800 条（约2.5年），更早需分段获取

### 2. 指标层 — strategy_library（真相源）

**所有新代码从 `strategy_library.indicators` 导入。`indicators_tdx.py` 是向后兼容 wrapper。**

TDX 核心函数在 `strategy_library/_core.py`，各指标在 `strategy_library/indicators/_*.py`。

**5个指标**（3个 active + 2个待数据）：

| # | 函数 | 模块 | 状态 | 数据需求 |
|---|------|------|------|---------|
| 1 | `calc_zhuli_radar(df)` | `_zhuli_radar` | ✅ active | 仅 OHLCV |
| 2 | `calc_ai_activity(df)` | `_ai_activity` | ✅ active | 仅 OHLCV |
| 3 | `calc_gs_signal(df)` | `_gs_signal` | ✅ active | 仅 OHLCV |
| 4 | `calc_dark_pool(df, mf_df)` | `_dark_pool` | ✅ active | moneyflow_daily 已有数据 |
| 5 | `calc_zhuli_holdings(df, mf_df)` | `_zhuli_holdings` | ✅ active | moneyflow_daily 已有数据 |

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

#### v4 多票组合策略（`backtest_v4.py`, ~530行）— **当前主力**

精简策略，GS + 主力雷达双指标，多票组合管理，经过5轮迭代。

**当前参数（`config.V4_PARAMS`）**：
- **买入**：GS在G区间 AND 主力线上穿零轴 → 次日开盘买入
- **卖出**（任一触发）：-8%硬止损 / 主力线连降4日 / 利润峰值回调5%
- **豁免**：盈利>10%持股不卖，利润从峰值回调5%才卖
- **组合**：最多3只，每只1/3仓位，按主力线上涨幅度排序，卖出后10天冷静期

⚠️ **调参铁律**：参数敏感性极高，必须逐个参数单独回测对比，不要批量改动。连降天数从2→3→4，收益率从+9%→跳过→+230%。每次只改一个参数。

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

### 5. 数据库

`stock_data.db`（SQLite, 53MB, 14张表）：

| 表 | 行数 | 说明 |
|----|------|------|
| `daily_kline` | 44,470 | 307只股票日线 |
| `moneyflow_daily` | 215+ | 99只自选股主力/大单/中单/小单资金流（东方财富API） |
| `minute_kline` | 243,435 | 1分钟线 |
| `minute5_kline` | 58,176 | 5分钟线 |
| `v4_backtest_results` | — | v4回测结果（bridge.py写入） |
| `backtest_results` | 3 | 旧 backtrader 回测结果 |
| `valuation_results` | 6 | 估值分析结果 |
| 其他 | — | 股本结构、股东户数、ROE、营收、REITs、可转债 |

**moneyflow_daily 资金流管线**：
- 数据源：东方财富 `push2his.eastmoney.com`（⚠️ 本地 curl 不通，需通过 Hermes `web_extract` 访问）
- API 格式：`lmt=3&klt=1&secid=0.{code}&fields2=f51,f52,f53,f54,f55,f56,f61,f62&fmt=json`
- Cron job `209c43908019`：每日 18:30 拉取 STOCKS_V4 全部 99 只股票最新 3 日资金流
- 字段映射：f52=主力净流入, f53=超大单净流入, f54=大单净流入, f55=中单净流入, f56=小单净流入
- `web_extract` 取得原始 JSON 上限约 50 行（lmt>50 会被 LLM 摘要而非返回原始数据）
| 其他 | — | 股本结构、股东户数、ROE、营收、REITs、可转债 |

每日 cron job (`fda7975b8524`) 自动增量更新。新增自选股后下次 cron 运行时会自动补全历史数据。

### 添加自选股

1. `config.py` → `STOCKS_V4` dict 新增 `"代码": "名称"`
2. `bridge.py --sync-watchlist` 同步到 `web_data/watchlist.json`
3. 下次 cron job 运行时会自动拉取该股历史数据
4. 更新 Hermes memory 中的自选股列表

无需手动 `fetch_daily_kline` — cron job 自动处理。

## 已知问题

1. **腾讯API最多800条记录** — 约2.5年，更早历史需分段获取
2. **v4 主力线连降参数敏感** — 连降天数2→4使收益率从+9%跳到+230%，必须逐个参数调
3. **venv 是 Python 3.9**（不是 3.11）— `data_manager.py` 的 `__pycache__` 中有 `.cpython-311.pyc` 混入，但不影响运行
4. **Cron 脚本必须用 shell wrapper** — 系统 Python 缺少 pandas，`.py` 脚本必须通过 `daily_update_v2.sh`（在 `~/.hermes/scripts/`）包装，显式调用 `.venv/bin/python`。✅ 已修复，当前 cron `last_status: ok`。
5. **Git push 代理降级** — git 全局配置了 Karing 代理，定时任务运行时代理未必在线。push 脚本已有降级 fallback（直连）
6. **东财API网络限制 + moneyflow_daily 已填充**：暗盘资金/主力持仓可从降级模式切换到完整模式。数据源：东方财富 `push2his.eastmoney.com`。本地 curl/Python urllib 能完成 TLS 握手但服务器返回空回复；Hermes 中继 `web_extract` 可正常访问，需 `lmt≤50` + `fmt=json` 获取原始 JSON。增量更新由 cron `209c43908019` 每日 18:30 自动执行。详见 `references/moneyflow_pipeline.md`。

## 亏损诊断流程

当策略在特定股票上亏损时，三步诊断：

1. **检查买入持有收益**：区分是熊股拖累还是策略问题
2. **逐笔交易分析**：买入zhuli值、持仓峰PnL、卖出zhuli值、持有天数
3. **模式识别**：信号簇聚 / 高位接盘 / 卖出太晚

脚本：`analyze_losers.py`（已迁入 `~/my_quant_system/`）。

## 文件参考

- `references/strategy_library_architecture.md` — 🆕 策略武器库架构、添加新指标模板、暗盘资金适配方案
- `references/systems_relationship.md` — 与 daily_stock_analysis 的关系 + SQLiteFetcher 桥接方案
- `references/ths_indicators_guide.md` — 每个指标的逐行公式→Python映射
- `references/v4_gs_zhuli_strategy.md` — v4策略设计文档和迭代历程
- `references/rule_engine_strategy.md` — v3规则引擎完整设计
- `references/tencent_data_api.md` — 腾讯 ifzq API 文档
- `references/unified_system_files.md` — 统一后完整文件清单
- `references/moneyflow_pipeline.md` — 东方财富资金流数据管线：API端点、字段映射、网络限制与替代方案、数据覆盖

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
