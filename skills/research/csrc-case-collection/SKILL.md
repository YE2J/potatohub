---
name: csrc-case-collection
description: 从中国证监会网站采集高质量操纵证券市场行政处罚决定书，含反爬安全策略、两级筛选引擎、本地 SQLite 存储与分析管线。
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [macos]
metadata:
  hermes:
    tags: [CSRC, 证监会, 操纵市场, 行政处罚, 爬虫, 案例库]
---

# CSRC 操纵市场案例采集

## 触发条件

当用户提到以下任一关键词时加载：
- "证监会处罚" / "证监会案例" / "CSRC"
- "操纵市场" / "操纵证券市场"
- "行政处罚决定书"采集
- "江勇案级别" / "天山生物案"

## 核心设计原则

1. **反爬安全第一，速度完全不重要**。政府网站，宁可慢十倍不可封一次。
2. **代码能做的一律不调 LLM**。粗筛 0 Token 完成 80-90% 过滤。
3. **目标案例画像**：操纵证券市场类，含秒级时间戳、手法拆解、账户控制、申辩复核攻防——以江勇操纵"天山生物"案（〔2021〕76号）为标杆。

## 已建好的基础设施

| 文件 | 用途 |
|------|------|
| `~/my_quant_system/case_library/schema.sql` | 完整 DDL（6表+FTS5+视图） |
| `~/my_quant_system/case_library/db.py` | `CaseDB` 类（CRUD/搜索/筛选/统计/导出） |
| `~/my_quant_system/case_library/case_library.db` | SQLite 空库（已初始化） |
| `~/my_quant_system/docs/case_storage_design.md` | 存储设计文档 |

使用方式：
```python
from db import CaseDB
db = CaseDB()
db.init_schema()
db.insert_case({...})
db.search_by_method("涨停板撤单")
db.filter_cases(violation_type="操纵证券市场", year_from="2021")
```

## 采集架构

```
列表发现(URL)  →  正文提取(全文)  →  粗筛(0Token)  →  精筛(低Token)  →  保存(CaseDB)
    ↑                   ↑                ↑                ↑               ↑
Selenium+JS       web_extract       信号评分系统      LLM JSON输出    insert_case+
(必须是JS)        (纯HTTP即可)      过滤80-90%        ~1750t/篇      save_llm_extraction
```

### 已验证的 URL 模式

- **详情页**：`http://www.csrc.gov.cn/csrc/c101928/c{ID}/content.shtml`
  - ID 有两种：纯数字（c7521308）和 UUID（c4901927...）
  - `web_extract` 可直接提取全文，**不需要 Selenium**
  - 正文选择器：`div.detail-news`

- **列表页**：`http://www.csrc.gov.cn/csrc/c101925/zfxxgk_zdgk.shtml?channelid=...`
  - ⚠️ 需要 JavaScript 渲染（必须用 Selenium）
  - 翻页：点击"下一页"链接
  - 列表行选择器：`#codeId_list > ul > table > tbody > tr`
  - 参考：GitHub Gist `goldluo126/718bb567c142b7194c7d10758a2a7221`（2023年的 Selenium 爬虫）

- **❌ 豆包方案的 URL 已验证为错误**：`zfxxgk_zdlist_{page}.shtml` 不返回处罚列表

### 反爬策略（关键！）

| 维度 | 策略 |
|------|------|
| 详情页间间隔 | ≥ 5 秒 |
| 翻页间隔 | ≥ 10 秒 |
| 运行时间窗口 | 仅工作日 9:00-18:00 |
| 单次上限 | ≤ 2 小时，每天 ≤ 1 次 |
| 单日总量 | ≤ 200 篇 |

**紧急熔断**：
- 连续 3 次 403/503 → **立即停止，24h 禁重试**
- 出现"验证码"/"访问过于频繁" → **72h 禁重试**
- 单日达 200 篇 → 自动停止

**Selenium 反检测**：`--disable-blink-features=AutomationControlled` + 随机窗口尺寸 + 模拟正常人类行为。

## 筛选规则引擎

### 第一层：代码粗筛（0 Token）

**一票否决**（任一命中 → 丢弃）：
- 字数 < 1500
- 非"操纵证券市场"类型（用关键词指纹法分类）
- 表格/纯数据格式（数字密度 > 0.25 且无叙事段落）
- 句号数 < 15

**信号加权评分**（满分 ~80，通过线 ≥ 45）：

| 信号 | 权重 | 检测方式 |
|------|:---:|------|
| 秒级时间戳 `\d{2}:\d{2}:\d{2}` | 5.0 | 正则 |
| 手法拆解（拉升/封单/撤单/出货） | 4.0 | 关键词组合 |
| 申辩复核攻防 | 4.0 | "当事人"+"申辩"+"复核" |
| 账户控制细节 | 3.5 | "实际控制的账户"/"账户组" |
| 成交量/金额明细 | 3.0 | "万股"/"亿元" |
| 多日序列（≥3天） | 3.0 | 日期序列检测 |
| 字数梯度 | 1.0 | min(len/8000,1)×10 |

**高价值信号组合**：`时间戳秒级 + 手法拆解 + 申辩复核` → 99% 命中目标。

### 第二层：LLM 精筛（~1750 Token/篇）

只送智能截取的 ~3300 字（头部500 + 中间2000 + 尾部800），强制 JSON：

```json
{"score": 0-100, "level": "A|B|C|D", "verdict": "keep|drop",
 "features": {"has_timeline": bool, "timeline_granularity": "second|minute|day|none",
              "has_method_decomposition": bool, "has_account_control": bool,
              "has_defense_review": bool, "trading_days_count": int}}
```

**预估效果**：1000 篇 → 粗筛后 80 篇 → 精筛后 50 篇。Token 消耗从全量 LLM 的 500 万降至 8.75 万（节省 96.5%）。

## 违法类型自动分类（关键词指纹法）

```
操纵证券市场 ← "实际控制的账户" "对倒/对敲" "封单/撤单" "涨停板出货" "虚假申报"
信息披露违规 ← "信息披露" "未按规定披露" "定期报告" "重大遗漏" "虚假记载"
内幕交易     ← "内幕信息知情人" "非法获取内幕信息" "建议他人买卖"
其他         ← "短线交易" "老鼠仓" "出借账户" "代客理财"
```

标题关键词权重 ×3，正文 ×1。若操纵类关键词命中 < 3 个 → 退回第二高分类型。

## 存储 Schema 亮点

- **6 表**：cases / case_parties / case_penalties / case_related_securities / case_tags / case_llm_extraction
- **FTS5 全文搜索**：cases_fts（标题/摘要）+ llm_extraction_fts（手法/过程/证据）
- **3 个分析视图**：v_case_full / v_method_trend / v_top_penalties
- **去重**：URL + 文号 + 内容哈希三层
- **采集日志**：collection_log 表追踪每篇状态

## 待完成

| 优先级 | 任务 |
|:---:|------|
| P0 | 编写 `collect_csrc.py`（Selenium 列表 + web_extract 详情 + 反爬） |
| P0 | 编写 `screener.py`（两层筛选引擎） |
| P0 | 检查 robots.txt |
| P1 | 接入 CaseDB 保存管线 |
| P1 | 小批量验证（1页 ≈ 20 篇） |
| P2 | cron 定时任务配置 |

## 内置支持文件

| 文件 | 用途 |
|------|------|
| `references/csrc-url-structure.md` | CSRC 网站 URL 结构勘验记录（已验证/已验证错误） |
| `references/signal-scoring-detail.md` | 信号评分系统详解（硬性排除+加权评分+LLM精筛） |
| `references/anti-crawling-strategy.md` | 反爬安全策略（频率控制+反检测+Selenium配置+熔断） |
| `templates/collect_csrc.py` | 采集脚本模板（Selenium列表+HTTP详情+熔断+CSV存储） |

## 相关参考

- GitHub 参考爬虫：`goldluo126/718bb567c142b7194c7d10758a2a7221`（2023年，Selenium+BeautifulSoup）
- 标杆案例 URL：`https://www.csrc.gov.cn/csrc/c101928/c1782468/content.shtml`（江勇案）
- 数据库位置：`~/my_quant_system/case_library/`
