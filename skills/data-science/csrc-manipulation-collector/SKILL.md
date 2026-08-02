---
name: csrc-manipulation-collector
description: "CSRC 操纵证券市场案例采集：发现→下载→筛选→入库，支持 web_search 替代方案"
version: 1.0.0
platforms: [macos]
metadata:
  hermes:
    tags: [CSRC, 证监会, 操纵市场, 采集, 筛选]
    category: data-science
    related_skills: [hermes-macos-sandbox, a-share-research]
---

# CSRC 操纵证券市场案例采集

完整的证监会行政处罚决定书采集管线，专为**操纵证券市场**类型的高质量详案设计。

## 触发条件

- 用户说"采集证监会案例""收集CSRC处罚""操纵市场案例"

## 系统架构

```
发现 URL → 下载详情 → 粗筛过滤 → LLM精筛 → 入库存储
─────────────────────────────────────────────────
web_search   web_extract  screener.py  Hermes LLM  CaseDB
(0 Token)    (0 Token)    (0 Token)   (低Token)   (0 Token)
```

## 代码位置

```
~/my_quant_system/case_library/
├── collect_csrc.py      # 采集脚本 (Selenium列表 + HTTP详情)
├── screener.py          # 筛选引擎 (9信号 + 硬排除)
├── pipeline.py          # 编排管线
├── db.py                # CaseDB 数据库访问层
├── schema.sql           # DDL
├── case_library.db      # SQLite 数据库
├── raw_text/            # 清洗后文本
└── raw_html/            # 原始HTML
```

## 采集方法

### 方法A：Selenium 列表页采集（需 Chrome）
```bash
PY=~/.hermes/python-standalone/cpython-3.11.15-macos-aarch64-none/bin/python3
$PY ~/my_quant_system/case_library/collect_csrc.py --pages 3
```

### 方法B：web_search + web_extract 替代方案（无需Chrome）
当 Selenium/Chrome 不可用时，用 Hermes 内置工具：
1. `web_search("site:csrc.gov.cn/c101928 操纵证券市场")` 发现URL
2. `web_extract(urls=[...])` 下载详情全文
3. 手动保存文本 → 跑筛选器

**CSRC URL结构：**
- 列表页：`http://www.csrc.gov.cn/csrc/c101925/zfxxgk_zdgk.shtml?channelid=29ae08ca97d44d6ea365874aa02d44f6`（JS渲染，需Selenium）
- 详情页：`http://www.csrc.gov.cn/csrc/c101928/c{ID}/content.shtml`（纯HTTP，web_extract直接拿）
- ⚠️ 豆包方案给的 `zfxxgk_zdlist_{page}.shtml` 是**错的**

## 筛选规则

### 两层筛选

**第一层：代码粗筛（0 Token）**
- 硬排除：字数<1500 / 句数<15 / 非操纵市场类型 / 表格格式 / 句均字数<25
- 9信号评分（满分~35.5）：
  - timestamp_second (5.0): 秒级时间戳 `HH:MM:SS`
  - timestamp_density (1.5): 每千字≥2个
  - method_decomposition (4.0): 拉升/封单/撤单/涨停板出货/对倒/虚假申报
  - defense_review (4.0): 申辩+复核或不予采纳
  - account_control (3.5): 账户组/控制使用
  - volume_detail (3.0): 万股/亿元等
  - multi_day_sequence (3.0): 多日序列
  - structure_completeness (1.5): 经查明+违法事实+处罚决定
  - word_count_quality: min(len/8000,1)×10
- **阈值：21.0**

**第二层：LLM精筛（低Token）**
- 仅输入智能截取的~3300字
- 强制JSON输出评分
- 用于捞回17-21分的长线持仓型

### 两类操纵案

| | 短线Pump&Dump | 长线持仓操纵 |
|------|:---:|:---:|
| 标杆 | 江勇 天山生物 | 余韩 博士眼镜 |
| 评分 | 27+ | 17-21 |
| 时间戳 | ✅ 秒级 | ❌ |
| 手法链 | ✅ 拉升→封单→撤单 | ❌ 持股优势+对倒 |
| 账户 | 4个 | 67个 |
| 周期 | 4天 | 1252天 |
| 入库 | 直接 | LLM精筛后决定 |

### 关键词分类器

操纵市场关键词：`操纵证券 操纵市场 连续买卖 账户组 涨停板 封单 撤单 拉抬 虚假申报 对倒 集中资金优势 持股优势 在自己实际控制的账户`

## Python 环境

- 独立Python：`~/.hermes/python-standalone/cpython-3.11.15-macos-aarch64-none/bin/python3`
- 脚本放 `~/.hermes/scripts/` 内（sandbox安全）
- 已装：requests, beautifulsoup4, lxml, selenium
- Selenium需Chrome浏览器（本机未装）

## 反爬安全

- 详情页 ≥5s间隔，翻页 ≥10s
- 单次≤200篇，≤120分钟
- 连续3次错误→24h冷却
- 仅工作日9:00-18:00运行
- 受 Hermes macOS sandbox 约束（见 hermes-macos-sandbox skill）

## 后续分析

CaseDB 支持：
- 全文搜索手法：`db.search_by_method("涨停板撤单")`
- 多条件筛选：`db.filter_cases( violation_type="market_manipulation", year_from="2024")`
- 年度统计：`db.yearly_stats()`
- 导出Markdown：`db.export_case_markdown(case_id)`
