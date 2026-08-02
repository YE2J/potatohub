# C组项目评估参考 (2026-07-04)

评估4个A股量化金融开源项目，涵盖安装必要性、借鉴价值和跨组综合判断。

---

## 1. YUHAI0/fin-agent (⭐290)

| 维度 | 详情 |
|------|------|
| 描述 | DeepSeek+多LLM驱动的自然语言金融分析助手。行情查询、财务分析、宏观数据(GDP/CPI/M2)、智能选股器、20+策略回测引擎、模拟投资组合、股价预警、用户画像。pip安装。有Electron桌面版。 |
| 技术栈 | Python, Tushare, DeepSeek/Kimi/GLM-4/Qwen等多LLM, pip |
| 兼容性 | 兼容Tushare，但偏LLM对话式，与自实现pandas+numpy+SQLite路线差异大 |
| 借鉴点 | 自然语言选股→筛选参数转换、20+内置策略实现、用户画像记忆 |
| 安装必要 | 低 — 用户已有自实现ic_analyzer/backtest_v4，该项目的回测引擎不如现有体系深入 |
| 推荐度 | ⭐⭐⭐ |

## 2. shouldnotappearcalm/a-share-skill (⭐190)

| 维度 | 详情 |
|------|------|
| 描述 | 两个核心Skill：a-share-data(实时行情/K线/技术指标/事件/行业/指数/宏观) + a-share-paper-trading(模拟账户/下单/持仓/回测)。轻量模块化，专为Claude Code/Cursor/Codex设计。模拟交易2个月+40%。 |
| 技术栈 | Python, akshare, 轻量Skill格式(文件复制安装) |
| 兼容性 | 用akshare非Tushare。但Skill模块化理念与轻量自实现路线高度契合 |
| 借鉴点 | Skill架构设计(极简/模块化/可组合)、模拟交易系统、技术指标skill化封装 |
| 安装必要 | 中 — 不建议直接装(数据源akshare)，但强烈建议借鉴Skill设计理念 |
| 推荐度 | ⭐⭐⭐⭐ |

## 3. Yourdaylight/stock_datasource (⭐161)

| 维度 | 详情 |
|------|------|
| 描述 | "赛博操盘手"—AI原生多Agent金融分析系统。配置化Agent平台(10Agent+6Team)、三层架构(执行→分析→决策)、智能选股/K线可视/策略回测/多Agent竞技场/RPS排序/哨兵系统/微信联动。 |
| 技术栈 | Python, Tushare, ClickHouse+Redis+Docker, LangGraph, MCP Server |
| 兼容性 | 技术栈严重冲突(ClickHouse vs SQLite, Docker vs 轻量)，架构臃肿 |
| 借鉴点 | Agent Team三层架构、哨兵多数据源并行扫描设计、多Agent竞技场概念 |
| 安装必要 | 低 — 架构太重，Docker+ClickHouse非用户路线 |
| 推荐度 | ⭐⭐ |

## 4. HiThink-Tech/Financial-API (⭐136) — 同花顺官方

| 维度 | 详情 |
|------|------|
| 描述 | 同花顺官方金融数据API。REST(23端点)+MCP(22工具)+Agent Skill+Python CLI+本地DuckDB marketdb。A股行情/财务报表/财务指标/复权/交易日历/指数/涨停/异动/热榜/龙虎榜。全市场10年日K Parquet导出+增量自动同步。 |
| 技术栈 | Python, DuckDB, MCP, REST API, Parquet |
| 兼容性 | 部分兼容。DuckDB与SQLite语法基本兼容。同花顺官方数据更权威 |
| 借鉴点 | 本地marketdb(DuckDB+增量同步)、增量同步机制(FULL/INCREMENTAL/SKIP)、Agent Skill规范、同花顺涨停/异动/龙虎榜差异化数据、API Key管理 |
| 安装必要 | 中 — 战略价值。涨停/异动/龙虎榜/热榜数据填补Tushare缺失的数据空白 |
| 推荐度 | ⭐⭐⭐⭐ |

---

## 跨组综合

| 项目 | 推荐度 | 一句话 |
|------|--------|--------|
| Financial-API | ⭐⭐⭐⭐ | **最值得安装** — 拿同花顺官方数据补Tushare短板 |
| a-share-skill | ⭐⭐⭐⭐ | **最值得借鉴** — Skill模块化理念与用户轻量路线完美匹配 |
| fin-agent | ⭐⭐⭐ | 策略实现可参考，但不必装 |
| stock_datasource | ⭐⭐ | 架构太重，看看Agent Team设计理念就好 |
