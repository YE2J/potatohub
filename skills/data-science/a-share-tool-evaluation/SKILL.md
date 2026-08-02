---
name: a-share-tool-evaluation
description: 评估第三方A股量化工具/框架是否适合集成到用户现有的SQLite+pandas量化系统中。涵盖兼容性审查、功能匹配度、风险评估和替代方案建议。
---

# A-Share Tool Evaluation

评估第三方开源量化金融工具/框架是否值得引入用户的 `~/my_quant_system`。

## 评估触发条件

当用户询问对某个量化框架/工具的看法时：
- "帮我看看 X"
- "对比一下 X 和 Y"
- "X 怎么样/好不好用"
- "要不要试试 X"
- "X 和 Y 哪个更适合"

## 前置步骤：先摸清自己的系统

在审查任何第三方工具之前，先了解用户已有的基础设施。每次评估都要读取以下关键文件：

```bash
ls ~/my_quant_system/strategy_library/_core.py       # 通达信原语层
ls ~/my_quant_system/strategy_library/indicators/     # 自定义指标
ls ~/my_quant_system/bridge.py                        # 管线骨架
ls ~/my_quant_system/strategy_library/evaluation/     # 评估模块
ls ~/my_quant_system/strategy_library/_catalog.py     # 武器库目录
```

特别是 **`_core.py`** — 它等价于 MyTT 的全部功能（TDX_SMA/EMA/MA/CROSS/HHV/LLV/REF/SUM/IF/COUNT/MAX/MIN）。如果工具的核心能力仅是标准 TDX 指标计算，那用户已经有完整实现，不需要引入任何外部依赖。

## 评估方法论

### 1. 获取代码（非仅读README）

```bash
cd /tmp && git clone --depth 1 <repo-url>
```

深度有限克隆，不拉全量历史。

### 2. 宏观评估

- **README 诚实度**：作者是否承认已知问题（致命信号：作者说"代码跑不了"）
- **版本号**：`__version__` < 1.0 的 pre-alpha 项目需高度警惕
- **最近提交/Star数**：单人项目 vs 社区项目
- **协议**：GPL-3.0 有商业传染风险

### 3. 代码结构扫描

```bash
find /tmp/<repo>/<package> -maxdepth 3 -type f -name "*.py" | sort
find /tmp/<repo> -maxdepth 1 -type f -name "*.md" -o -name "*.py" -o -name "*.toml" -o -name "*.cfg"
```

关注核心模块路径：

| 模块 | 典型路径 | 检查要点 |
|------|---------|---------|
| 因子计算 | `factor/alphaEngine.py` | 公式引擎复杂度、回测风格 |
| 因子挖掘 | `factor/factorMining.py` | 是遗传编程/LLM/统计方法？ |
| 因子分析 | `factor/factorAnalyzer.py` | IC计算、分层回测 |
| 回测引擎 | `trader/default_trader.py` | 事件驱动/向量化 |
| 数据层 | `library/mydb.py` | 支持的数据库类型 |
| 基础设施 | `core/core.py` | 项目创建流程、CLI |

### 4. 五大维度兼容性审查

#### 4.1 数据库兼容性
用户的 stock_data.db 是 **SQLite**。检查工具的抽象层：
- `mydb.py` / 类似模块 是否支持 SQLite？
- 如果不支持（只支持 MySQL/DuckDB），数据迁移成本估算
- **不兼容是致命伤**，除非用户愿意迁移数据库

#### 4.2 依赖规模
用户的系统原则：**纯 pandas + numpy + 标准库**，零重型框架。
- 检查 `requirements.txt` 包数
- 关注：dask, redis, flask, lightgbm, alphalens, ta-lib 等重型依赖
- Python 版本兼容性（尤其是 ta-lib ≥ 3.11）
- **> 15 个依赖且含框架级组件** → 需警告

#### 4.3 架构兼容性
- 用户：独立脚本 + SQLite，文件级组织
- 工具：是否需要"创建项目目录"、CLI 初始化、动态生成 runtime 文件
- 学习成本评估

#### 4.4 数据管线兼容性
- 用户：`factor_pipeline.py` 自研，threadpool 并行，每日增量写入
- 工具：是否需要独立数据采集器（如 Tushare collector）、格式转换
- 两套管线能否共存

### 4.5 功能匹配度
- **核心问题**：工具宣称的"因子挖掘"是否等于用户需要的功能？
- 常见误区：符号回归/遗传编程 ≠ "给定买卖点，反向找影响因子"
- 区分：无监督 Alpha 生成 vs 有监督特征归因

### 4.6 指标库 vs 框架 — 区分类型

不是所有工具都是"框架"。按覆盖范围分为两类，评估方法不同：

| 类型 | 代表 | 评估方式 |
|------|------|----------|
| **重型框架** | FinHack, Qlib, RD-Agent | 5维度全面审查，关注兼容性/运行状态/依赖规模 |
| **轻量指标库** | MyTT, ta-lib, pandas-ta | 仅需判断"用户是否已有等价实现" |

**轻量指标库的评估逻辑**：
1. 读用户 `_core.py` — 如果用户的 TDX 原语层已覆盖 MyTT 的全部函数（SMA/EMA/MA/CROSS/HHV/LLV/REF/SUM/IF/COUNT），则标准指标（MACD/KDJ/RSI/BOLL）每个不到10行，不值得引入外部依赖
2. 轻量指标库的价值上限 = **参考实现** — 当需要复刻一个新指标时，打开它的源码看公式，然后用自己的 `_core.py` 原语实现
3. 评估结论通常是："可以作为公式参考，不引入为运行时依赖。把 MyTT 加入 `requirements-dev.txt` 或作为 knowledge reference"
4. 如果用户已经实现较复杂的自定义指标（如 GS信号、主力雷达），标准指标的追加更不值得引入外部依赖

## 深度阅读关键文件

每次评估至少阅读：
1. `requirements.txt` — 依赖清单
2. `setup.py` — 包架构
3. 核心模块的 `__init__.py` — 导出
4. 因子挖掘模块 — 用户最关心的能力
5. 回测引擎骨架 — 复杂度评估
6. 数据库抽象层 — 兼容性核心

## 输出结构化报告

采用以下评分标尺：

| 维度 | 评分(0-10) | 说明 |
|------|-----------|------|
| 功能匹配度 | N | 是否解决用户具体需求 |
| 技术栈兼容性 | N | 数据库/依赖/架构 |
| 代码可用性 | N | 能否直接运行 |
| 学习成本 | N | 引入成本 |
| 维护状况 | N | 作者活跃度 |
| **综合** | **N/10** | 推荐/不推荐 |

结尾必须给出**可操作替代方案**，而不是只说不。

---

## 第二类评估：商业 API/数据源评估

当用户询问的是 **API 服务 / 付费数据源 / 商业数据平台**（如同花顺 Financial-API、Tushare Pro、万得 Wind、东方财富 Choice）而非开源框架时，评估方法完全不同。

### API 评估与框架评估的核心区别

| 维度 | 开源框架/工具 | 商业 API/数据源 |
|------|--------------|----------------|
| **评审重点** | 代码质量、架构、依赖 | **数据覆盖**、接口设计、更新时效 |
| **核心产出** | 安装/不安装/读源码不安装 | **集成方案**: 新表设计 + 更新调度 |
| **源码审查** | 需要（deep dive） | 不需要（看文档 + 试 CLI 即可） |
| **兼容性** | 依赖/数据库/架构兼容性 | 已有 schema 的**重叠 vs 补缺**分析 |
| **风险类型** | 代码不可运行、维护停滞 | 限频限流、数据延迟、服务停止 |
| **交付物** | 评分表 + 可操作替代方案 | **数据对照矩阵 + 表结构设计 + cron 调度方案** |

### 前置步骤：完整扫描现有 DB

在评估任何 API 之前，必须先了解已有系统有什么：

```bash
# 1. 获取全部表名和行数
sqlite3 ~/my_quant_system/stock_data.db ".tables"
sqlite3 ~/my_quant_system/stock_data.db "SELECT COUNT(*) FROM <table>" 2>/dev/null

# 2. 获取每张表的 CREATE TABLE 语句
sqlite3 ~/my_quant_system/stock_data.db ".schema <table>"

# 3. 查看数据来源 cron 管线
ls ~/.hermes/scripts/*.sh ~/.hermes/scripts/*.py
# 检查管线映射：哪个 cron job 写入哪张表

# 4. 检查现有数据覆盖率（最新日期、每日行数）
sqlite3 ~/my_quant_system/stock_data.db "
  SELECT 'daily_kline', MAX(date), COUNT(*) FROM daily_kline WHERE date = (SELECT MAX(date) FROM daily_kline)
  UNION ALL
  SELECT 'moneyflow_daily', MAX(date), COUNT(*) FROM moneyflow_daily WHERE date = (SELECT MAX(date) FROM moneyflow_daily)
  UNION ALL
  SELECT 'index_daily', MAX(trade_date), COUNT(*) FROM index_daily WHERE trade_date = (SELECT MAX(trade_date) FROM index_daily)
"
```

### 评估流程

#### 1. 能力映射（遍历 API 端点到列表）

列出 API 所有可用接口，与现有 DB 各表逐一比对：

```
API 端点                          → 对应现有表？       → 新表？
prices-historical                 → daily_kline       → (备源，冗余)
financials-income                 → A股营业总收入      → (扩充字段)
limit-up-pool                     → ❌ 无             → limit_up_pool ★
dragon-tiger-list                 → ❌ 无             → dragon_tiger_daily ★
```

**三分类结果**:
- 🔴 **独有数据**: 现有管线完全没有 → 高优接入（新表）
- 🟡 **重叠但差异大**: 有部分但格式/粒度不同 → 对齐后补充
- 🟢 **完全冗余**: 选一个为主，另一个为备源

#### 2. 集成方式评估

| 接入方式 | 适用场景 | 推荐度 |
|---------|---------|--------|
| **CLI 子进程** | Python 脚本调 shell | ★★★★★ — 零依赖，与现有 pipeline 风格一致 |
| **Python SDK** | 项目内 import | ★★★★☆ — 需安装依赖 |
| **REST API 直调** | 性能敏感场景 | ★★★☆☆ — 需自建请求/重试/鉴权 |
| **MCP Tools** | Agent 交互式查询 | ★★★☆☆ — 不适合批量管线 |

**用户系统优先使用 CLI 子进程**：与现有 `qfq_tushare_daily.sh` 等脚本风格一致，不增加依赖。

#### 3. 表结构设计

映射 API JSON 响应到 SQLite 表：

```python
# 原则：一次调用 → 一张表，不拆表
# 主键：复合主键 (trade_date, thscode) 为最优
# 字段：能存全量 JSON 的原始字段，不提前过滤

CREATE TABLE example_new_table (
    trade_date     TEXT NOT NULL,       -- 交易日 YYYY-MM-DD
    thscode        TEXT NOT NULL,       -- 同花顺代码 600519.SH
    stock_name     TEXT,                -- 股票简称
    ...                                -- 根据 API 响应字段逐一映射
    PRIMARY KEY (trade_date, thscode)
);
```

#### 4. 更新调度策略

| 策略 | 适用场景 | SQL 实现 |
|------|---------|---------|
| **增量** | 高频率、大体积 | `INSERT OR REPLACE` |
| **全量** | 低频率、小体积(滚动窗口) | `DELETE FROM ... WHERE trade_date < cutoff; INSERT ...` |
| **混合** | 增量+定期全量校验 | 增量为主 + 周/月级全量覆盖 |

**cron 调度模板**（Hermes cron 格式）:

```yaml
jobs:
  - id: 数据名称-数据源标记
    schedule: "MM HH * * 1-5"         # 只在交易日运行
    command: "bash ~/.hermes/scripts/daily_xxx.sh"
```

#### 5. 输出集成方案

最终产出为一份集成文档（非评分表），包含：

```
1. 数据来源对照矩阵（Tushare vs Financial-API 的全表对比）
2. 新表结构设计（含主键、索引建议）
3. 分工边界（哪个源负责什么，分界原则）
4. 更新调度表（每个表何时拉、什么策略）
5. 优先级排序（三档：高优短线/中优辅助/低优增强）
6. 风险与注意事项（限流、环境依赖、代码格式统一）

建议的下一实施步骤：以最长前3步的优先级起步，实现一个可验证的原型。
```

### API 评估的常见陷阱

- **不先看 DB schema 就设计新表**：必须先了解已有的表和字段，避免创建与现有表含义重叠但结构不同的表
- **高估 API 的"独家性"**：很多数据看似独家，实际可以从现有 source 计算推导（如连板数 = 连续涨停天数，可从 daily_kline 的 pct_chg 计算）
- **忽略数据格式一致性**：不同 source 对同一股票的代码格式可能不同（`600519.SH` vs `600519`），需统一转换层
- **CLI 的直接 stdout 捕获**：`subprocess.run` 的 `capture_output=True` 在输出过大时有死锁风险，推荐 `subprocess.check_output` + 文件重定向
- **Python 环境锁死**：fuyao.py 等 CLI 脚本可能依赖特定 Python 版本（如 3.11.11），Hermes venv 可能不兼容。优先用用户的 pyenv Python，在脚本头固定 `#!/path/to/pyenv/versions/3.11.11/bin/python3`

---

## 常见陷阱

- **只读README不读源码**：README 通常美化，源码才是真相。至少读因子挖掘和数据库层的源码。
- **忽略版本号**：< 0.1 的项目可能有未完成的根本性重构。
- **高估"因子挖掘"功能**：大部分开源项目的"因子自动挖掘"是基于遗传编程的符号回归，产出的是不可解释的数学公式，不是用户想要的"给定买卖信号找因子"。
- **忽略协议**：GPL-3.0 在商业场景下有传染风险。
- **低估数据迁移成本**：即使工具功能完美，从 SQLite 迁移到 MySQL/DuckDB 可能比学工具本身更耗时。
- **无视"作者声明项目不能跑"**：如果 README 明确说"代码跑不了，正在重构"，直接判定为不可用。不要试图相信"也许下次commit就好了"。
- **不查自己已有的核心层就评估指标库**：用户的 `_core.py` 已经实现了 MyTT 全部的 TDX 原语。如果评估 MyTT 或类似指标库（pandas-ta/ta-lib）时不先读 `_core.py`，就会给出 "引入外部依赖" 的错误建议。
- **把指标库等同于策略能力**：标准 TDX 指标（MACD/KDJ/RSI/BOLL）和用户的自定义指标（GS信号/主力雷达/暗盘资金）是两回事。用户的核心策略依赖的是同花顺LV2付费信号的复刻，任何标准指标库都不能替代这个能力。

## 用户系统快照

评估时参考的基础配置：
- 数据库：SQLite, `~/my_quant_system/stock_data.db` (~2.2GB)
- 因子管线：`factor_engine/factor_pipeline.py` + `strategy_library/factors.py`
- IC评估：`strategy_library/evaluation/ic_analyzer.py`（纯pandas, 628行）
- 回测：`backtest_v4.py`（纯pandas, ~685行）
- Python：3.11.11
- 数据来源：Tushare + 自有 moneyflow 管线
- 风格偏好：轻量、少依赖、可理解、SQLite落地

## 多项目批量对比评估

当用户要求评估 **多个项目**（3+）时，不能只是逐个独立评估。应采用**先过滤→后聚焦**的流水线：

### 第一步：快速初筛

对所有项目收集以下基本指标，快速排除明显不合适的：

| 指标 | 危险信号 | 通过条件 |
|------|---------|---------|
| 技术栈 | Java/C++/TypeScript/Go 非 Python | 仅 Python 可进入人工审查阶段 |
| 数据源锁定 | 仅支持同花顺通达信/非Tushare/tickflow 独有 | 支持 Tushare 或通用接口 |
| 最后更新 | > 6 个月未更新 | 近 3 个月有实质更新 |
| Star 数 | < 200 | > 300 社区验证基本可靠 |
| 框架重量 | 需要额外数据库/服务器/前端部署 | 纯 Python 代码即可运行 |

**技术栈不匹配是致命伤，直接跳过**：TypeScript/Java/C++ 意味着跨语言维护，用户纯 Python 生态无法吸收。这类项目只看前端/设计理念，不做深度代码审查。

### 第二步：对通过初筛的项目做4维度审查

对每个项目记录：

1. **功能匹配度** — 是否解决用户的"买卖点→因子挖掘"核心需求
2. **技术栈兼容性** — 数据库/依赖/架构/语言
3. **值得借鉴的点** — 即使不安装，有什么设计/算法/思路值得阅读源码
4. **安装必要性** — 明确给出：安装 / 选择性实验 / 源码阅读不安装 / 跳过

### 第三步：产出比较矩阵

输出形式为 **对比表**，让用户一目了然：

| 项目 | 推荐度 | 建议行动 | 核心价值 |
|------|--------|----------|----------|
| A | ★★★★☆ | 架构实验 | 多agent协作管线 |
| B | ★★★☆☆ | 源码阅读 | 规则品类设计 |
| C | ★☆☆☆☆ | 跳过 | 技术栈不兼容 |
| D | ★★☆☆☆ | 风控参考 | 回撤管理算法 |

### 第四步：识别"借源码" vs "安依赖"的正确选择

这是最关键的区分——不要只回答"安装/不安装"。对于以下类型推荐"不安装但读源码"：

- **规则引擎类项目**（如UZI-Skill：180条规则）：读其规则设计思路，选择性移植到已有 strategy_library
- **LLM编排类项目**（如aiagents-stock）：读 agent 协作架构和 prompt 设计，不用跑其完整代码
- **风控模块**（如KHunter）：读回撤/止损算法，复用设计到自己的 backtest 管线
- **面板UI类**（如tickflow-stock-panel）：只读前端交互设计理念，不引入任何运行时依赖

关键问题：**"用户已经有什么？缺什么？"** 回答完这两个问题后，每个项目的"可借鉴点"自然浮现。

## 网络不可达时的评估替代方案

当 GitHub / raw.githubusercontent.com 无法访问时（API 限流、CDN 超时、防火墙拦截）：

1. **从用户提供的描述出发** — 用户请求中通常带了项目名称、star数、语言、简短描述
2. **结合已有知识** — 利用已知的同类项目特征做合理推断
3. **明确标注信息缺口** — 在报告中注明"未获取到源码，分析基于公开描述"
4. **建议事后补读** — 给出明确建议：需要clone哪几个项目做源码级评估
5. **优先关注 star/update 时间** — 这些即使通过搜索也能部分获取

当网络不可达时，分析应更保守（不推荐安装任何未读源码的项目），但借鉴价值仍可评估。

## 实施阶段（评估通过后）

当用户决定安装/集成某工具或数据源后，进入实施阶段。遵循 **实施→审查→修复→终验** 四段式流程。

### 四段式实施流程

评估通过 -> 实施A/B/C(并行) -> 审查A/B/C(并行) -> 修复(并行) -> 终验 -> 上线

每个阶段产出：
- **实施**: 产出代码/脚本/DB变更
- **审查**: 产出审查报告（严重bug/中等风险/改进建议）
- **修复**: 全部严重bug必须修，中等视情况
- **终验**: 语法检查 + 表结构验证 + 逻辑验证

### 多Agent并行实施模式

对于大型集成任务，按以下维度拆分并行：

| Agent | 负责 | 典型产出 |
|-------|------|---------|
| 实施A | 数据基础设施 | DB表创建 + ETL采集脚本 |
| 实施B | 策略增强 | signal_enhancer / 评分模块 |
| 实施C | 因子计算 | factors.py + ic_runner + IC验证 |

### 实施后审查要点

#### 1. DB schema vs API 字段映射（最常见bug）

实施Agent常犯的错误：按文档设计表，但API实际返回的JSON字段名不同。

**必须在实施前执行**：如果API提供商有 `llms.txt` / `llms-full.txt` 等AI专用文档，必须先下载保存到本地，作为字段映射的权威参考。
- 例：Financial-API 的 `https://fuyao.aicubes.cn/llms-full.txt` 包含完整的响应字段定义、参数说明、错误码
- 在Agent的系统提示中加入：`所有涉及X-API的工作，先查阅 <本地路径>llms-full.txt 确认字段名和参数`
- 不要依赖README或文档站的截图——llms-full.txt 是机器可读的权威来源

**必须验证**：先跑一次CLI看实际返回字段：
```bash
python fuyao.py <command> | python -c "import json,sys; d=json.load(sys.stdin); print(list(d.keys() if isinstance(d,dict) else d[0].keys() if d else 'EMPTY'))"
```

常见字段映射bug模式:
- daily_anomaly表设计了price/pct_chg/trigger_time但API返回tag_name/keyword_list/analysis_content
- dragon_tiger_daily的total_amount被删除后INSERT语句仍包含该列
- limit_up_pool的fd_amount未映射API的seal_money
- hot_stock_daily的涨跌幅/价格API不直接返回，需从日线JOIN

#### 2. SQL INSERT 列数与表结构一致

验证方法：
```sql
PRAGMA table_info(<table>);  -- 获取实际列
-- 对比 INSERT 语句的列列表
```

常见问题：修复Agent删了表列但没更新INSERT语句 -> 运行时SQLite报错。

#### 3. 股票代码格式一致性

| 来源 | 格式 | 示例 |
|------|------|------|
| Tushare (stock_code) | 带后缀 | 000001.SZ |
| Financial-API (thscode) | 带后缀 | 000001.SZ |
| watchlist 表 | 裸代码无后缀 | 000001 |
| daily_kline (stock_code) | 裸代码 | 000001 |

新旧表的代码格式不一致时，无法直接JOIN。需在ETL脚本中添加后缀补全逻辑。

#### 4. etl_runs 日志列名

已有 etl_runs 表的实际列名可能与新脚本假设的不同，必须先读表结构再写日志。

```sql
PRAGMA table_info(etl_runs);
-- 实际字段: run_id, job_name, trigger_type, started_at, finished_at, status, total_count, ...
```

#### 6. Look-ahead bias（未来函数）— 回测信号必须按当前日期取值

回测中信号值必须根据**回测当前日期**定位，不能从全量DataFrame的末尾取值。

```python
# ❌ 错误：取整个DataFrame最后一行（泄露未来信息）
zhuli_today = float(zhuli_series[-1])
yesterday_was_limit_up = df_stock.iloc[-2].get("close", 0)

# ✅ 正确：根据回测日期索引定位
current_idx = stock_data[code].index[date_idx]
zhuli_today = float(zhuli_series.loc[current_idx])
```

影响：所有 `iloc[-1]` / `iloc[-2]` / `values[-1]` 在回测循环中都是未来函数，必须修复。

#### 7. daily_factors vs daily_kline 日期格式不一致

`daily_factors.trade_date` 通常是 `YYYY-MM-DD` 格式，而 `daily_kline.date` 可能同时存在 `YYYYMMDD`（旧数据）和 `YYYY-MM-DD`（新数据）。两表LEFT JOIN时精确字符串匹配会失败。

```python
# merge前统一日期格式
f_df['date'] = f_df['date'].str.replace('-', '')
df['date'] = df['date'].str.replace('-', '')
# 或用 pandas to_datetime
df['date'] = pd.to_datetime(df['date'], format='mixed')
```

#### 5. NULL安全与默认值（数字0被`or`吞噬）

新表在非交易日可能无数据。所有读取新表的查询必须有默认值回退：

```python
# ❌ 错误：0 or 1 -> 1，丢了真实值0
open_times = r.get("open_times", 1) or 1

# ✅ 正确：显式区分None和0
open_times = r.get("open_times")
if open_times is None:
    open_times = 1
```

### 实施技术选型原则

| 选择 | 理由 |
|------|------|
| CLI子进程 | 与现有 no_agent cron 风格一致，零依赖 |
| INSERT OR REPLACE | 幂等，可重复运行 |
| 500条/commit | 批量写入性能与安全平衡 |
| 指数退避重试(3次) | 网络波动容忍，1s-2s-4s |
| set -e + cd防护 | shell脚本健壮性 |

### 注册cron

ETL脚本和shell wrapper就绪后，用 Hermes cron 注册为 no_agent 模式。

no_agent模式适用于纯脚本任务，不需要LLM推理，节省token。

## 参考案例

- `references/finhack-evaluation-20260704.md` — FinHackCN/finhack 完整评估记录（2/10不推荐），包含模块级源码分析和比较表。
- `references/mytt-evaluation-20260704.md` — mpquant/MyTT 轻量指标库评估记录，演示了"先查自己的核心层"评估方法。
- `references/batch-evaluation-bgroup-20260704.md` — B组4项目批量对比评估案例，演示了跨项目比较矩阵、"借源码vs安依赖"区分、技术栈不兼容处理。
- `references/financial-api-integration-20260704.md` — Financial-API 全量集成案例：数据源对照矩阵 -> 5张新表设计 -> ETL脚本 -> cron调度 -> 审查修复闭环（12个问题的完整生命周期）。
- **对比评估模板**：当用户要求对比多个工具（如"X vs Y"）时，评估结构应包含：
  1. 各自独立评估 -> 2. 逐一与用户现有系统对比 -> 3. 寻找重叠/空缺 -> 4. 综合推荐（推荐其中一个、都不推荐但提供替代方案、或仅作为参考）
  2. 关键问题："如果两个都不适合，用户已经有什么？还需要什么？"

## 用户工作流偏好

该用户偏好以下工作流（已多次验证）：
1. **先评审再干** — 不接受跳过评审直接实施。方案必须经过审查Agent评估后才进入编码阶段
2. **全部修完才验收** — 审查发现的问题必须全部修复，不遗漏严重bug
3. **多Agent并行** — 实施和审查都派多个Agent并行，提高效率
4. **四段式流程** — 实施 -> 审查 -> 修复 -> 终验，每段都有明确产出
5. **偏好表格化数据呈现** — 对比表、状态表、进度表清晰直观
