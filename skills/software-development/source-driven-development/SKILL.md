---
name: source-driven-development
description: Use when 用框架/API/数据源前先查官方文档再实现，不凭记忆。每个决策带可验证引用。
---

# Source-Driven Development（源驱动开发）

## 概述

每个框架/API/数据源相关的代码决策都必须有官方文档支撑。**不要凭记忆实现——验证、引用、让用户看到你的来源**。训练数据会过时、API 会被废弃、最佳实践会演变。这个 skill 保证交付的代码每个模式都能追溯到可验证的权威来源。

## 何时使用

- 用户要遵循某框架/数据源当前最佳实践的代码
- 写样板、starter 代码或会被项目复制的模式
- 用户明确要求"有文档的、验证过的、正确的"实现
- 实现官方推荐方式重要的功能（量化场景：数据源字段语义、指标口径、API 参数）
- 评审或改进用了框架特定模式的代码
- 任何即将凭记忆写框架特定代码的时刻

**何时不用**：正确性不依赖特定版本（重命名、修 typo、移动文件）、跨版本行为一致的纯逻辑、用户明确要速度优先。

## 流程

```
DETECT ──→ FETCH ──→ IMPLEMENT ──→ CITE
  │          │           │            │
  ▼          ▼           ▼            ▼
 什么栈？   抓相关官方   按文档模式   展示来源
            文档页       实现
```

### Step 1: 识别栈与版本

读依赖文件确定确切版本：

| 场景 | 依赖文件 | 对应栈 |
|:---|:---|:---|
| Python | `requirements.txt` / `pyproject.toml` | pandas/numpy/backtrader/tushare 等 |
| Node | `package.json` | React/Vue/Node |
| Go | `go.mod` | Go |
| Rust | `Cargo.toml` | Rust |

显式说明发现：

```
STACK DETECTED:
- pandas 2.2.0（requirements.txt）
- tushare 1.4.x
→ 抓取相关官方文档。
```

版本缺失或有歧义 → **问用户**。版本决定哪个模式正确。

### Step 2: 抓取官方文档

抓**具体功能对应的文档页**，不是首页、不是全套文档。

**权威来源层级（按优先级）：**

| 优先级 | 来源 | 示例 |
|:---|:---|:---|
| 1 | 官方文档 | tushare.pro/document、pandas.pydata.org/docs、docs.python.org |
| 2 | 官方博客/changelog | pandas 发布说明、tushare 更新公告 |
| 3 | 标准/规范参考 | SQLite 官方文档（sqlite.org）、HTTP/JSON 规范 |
| 4 | 运行时/兼容性 | 数据源接口说明页 |

**非权威——不得作为主要引用：**

- CSDN/掘金/知乎 博客教程（再热门也不行）
- 大模型生成的文档或摘要
- 自己的训练数据（这正是要验证的东西）

**抓取要精准：**

```
BAD:  抓 pandas 首页
GOOD: 抓 pandas.pydata.org/docs/reference/api/pandas.read_sql_query.html

BAD:  搜索"tushare 资金流怎么用"
GOOD: 抓 tushare.pro/document/2 对应 moneyflow 接口页
```

抓取后提取关键模式，注意弃用警告和迁移指引。官方来源互相矛盾时（迁移指南 vs API 参考），向用户说明差异，并对照检测到的版本验证哪个模式实际可用。

### Step 3: 按文档模式实现

- 用文档中的 API 签名，不用记忆中的
- 文档展示新方式 → 用新方式
- 文档废弃某模式 → 不用废弃版本
- 文档未覆盖 → 标记为 unverified

**文档与现有项目代码冲突时：**

```
CONFLICT DETECTED:
现有代码用 pro.daily 拉日线，但文档推荐 daily_basic（含估值字段）。
(Source: tushare.pro/document/2)

Options:
A) 用新模式（daily_basic）— 与当前文档一致
B) 匹配现有代码（pro.daily）— 与代码库一致
→ 你倾向哪种？
```

显式摆出冲突，不要静默选一个。

### Step 4: 引用来源

每个框架特定模式都要有引用，用户必须能验证每个决策。

**代码注释里：**

```python
# tushare 资金流主表：net_mf_amt 单位=元，主力净流入
# Source: https://tushare.pro/document/2?doc_id=170
df = pro.moneyflow_dc(...)
```

**对话里：**

```
我用 moneyflow_dc 代替 moneyflow_ths 做主数据源，因为 DC 口径单位为元、
量级真实（亿元级），THS 单位为万元需转换。
Source: https://tushare.pro/document/2?doc_id=170（字段单位说明）
```

**引用规则：**

- 完整 URL，不缩短
- 尽量深链带锚点（`#usage` 优于顶层页）
- 支持非显然决策时引用相关原文段落
- 找不到官方文档就明说：

```
UNVERIFIED: 未找到该模式的官方文档。
此实现基于训练数据，可能过时。生产使用前请验证。
```

对无法验证的事诚实，比虚假自信更有价值。

## 常见合理化借口（防自欺表）

| 借口 | 现实 |
|:---|:---|
| "我对这个 API 有信心" | 信心不是证据。训练数据里过时模式看起来正确但会崩。验证。 |
| "抓文档浪费 token" | 幻觉 API 更浪费。用户调试一小时然后发现函数签名变了。一次抓取省数小时返工。 |
| "文档不会有我要的" | 文档没覆盖本身就是信息——该模式可能不是官方推荐。 |
| "我提一句可能过时就行" | 免责声明没用。要么验证并引用，要么明确标 unverified。含糊最差。 |
| "这任务简单不用查" | 简单任务配错误模式会变成模板。用户的错误表单处理器被复制进十个组件后才发现现代做法。 |

## 红旗（Red Flags）

- 不查该版本文档就写框架特定代码
- 用"我记得/我认为"描述 API 而非引用来源
- 不知道模式适用于哪个版本就实现
- 引用博客/CSDN 而非官方文档
- 用训练数据里出现的已废弃 API
- 实现前不读依赖文件
- 交付无来源引用的框架特定决策
- 抓整个文档站，而只有一页相关

## 验证清单

- [ ] 从依赖文件识别了框架和版本
- [ ] 对框架特定模式抓取了官方文档
- [ ] 所有来源都是官方文档，不是博客或训练数据
- [ ] 代码遵循当前版本文档展示的模式
- [ ] 非平凡决策带完整 URL 来源引用
- [ ] 未使用已废弃 API（对照迁移指南检查）
- [ ] 文档与现有代码的冲突已摆给用户
- [ ] 无法验证的内容显式标记 unverified

*移植自 addyosmani/agent-skills（MIT），示例适配量化数据源场景（tushare/pandas/SQLite）。*
