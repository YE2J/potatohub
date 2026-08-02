---
name: csrc-penalty-collection
description: 中国证监会行政处罚决定书采集系统。安全爬取CSRC网站处罚决定书，两层筛选（代码粗筛+LLM精筛）定位高质量操纵市场详案，本地SQLite存储+分析。触发：证监会/CSRC/处罚决定书/操纵市场案例/采集行政处罚。
version: 1.0.0
metadata:
  hermes:
    tags: [CSRC, 证监会, 行政处罚, 操纵市场, 爬虫, 筛选, SQLite]
    related_skills: [a-share-research, announcement-search]
---

# CSRC 行政处罚决定书采集与筛选

## 触发条件

用户提到以下任意关键词时加载：
- 证监会处罚 / CSRC 处罚 / 行政处罚决定书
- 操纵市场案例 / 市场操纵 / 证券违法案例
- 采集证监会 / 爬取处罚决定书

## 核心原则

1. **安全第一，速度不重要**：政府网站，宁可慢十倍不可封一次
2. **代码能做的不调 LLM**：90% 工作零 Token，LLM 仅负责最终质量判断
3. **只采操纵市场高质量详案**：目标 = 江勇案级别（秒级时间线 + 手法拆解 + 申辩复核）
4. **合规边界**：仅采集公开信息、仅供个人研究、检查 robots.txt

## CSRC 网站结构（已验证）

| 页面 | URL 模式 | 渲染方式 |
|------|----------|----------|
| 列表页 | `csrc/c101925/zfxxgk_zdgk.shtml?channelid=29ae08...` | **JS渲染** → 必须 Selenium |
| 详情页 | `csrc/c101928/c{ID}/content.shtml` | 纯 HTML → `requests` 即可 |
| 详情正文 | `div.detail-news` | 已验证可用 |

⚠️ **豆包方案给的 URL 是错的**：`zfxxgk_zdlist_{page}.shtml` 不存在。

## 两层筛选体系

### 第一层：代码粗筛（0 Token）

硬性排除（任一命中→丢弃）：
- 字数 < 1500
- 非"操纵证券市场"类型
- 表格/纯数据格式（数字密度 > 0.25 且无叙事段落）
- 句号数 < 15

信号评分（总分 ≥ 22 通过，满分 ~36）：

| 信号 | 权重 | 检测方式 |
|------|:---:|------|
| 秒级时间戳 `\d{1,2}:\d{2}:\d{2}` | 5.0 | 正则 |
| 手法拆解（拉升/封单/撤单/出货） | 4.0 | 关键词 |
| 申辩复核攻防 | 4.0 | "当事人"+"申辩"+"复核" |
| 账户控制细节 | 3.5 | "实际控制的账户"/"账户组" |
| 成交量/金额明细 | 3.0 | `\d+[万多亿]?股` |
| 多日序列（≥3天） | 3.0 | 日期序列 |
| 时间戳密度（≥2/千字） | 1.5 | 计数/字数×1000 |
| 结构完整性（≥3/5标志） | 1.5 | 5个结构关键词 |
| 字数梯度 | ~0-10 | min(len/8000,1.0)×10 |

## 反爬安全策略

| 参数 | 值 |
|------|----|
| 详情页间隔 | 5-8 秒（随机） |
| 翻页间隔 | 10-15 秒（随机） |
| 单次上限 | 200 篇 / 120 分钟 |
| 运行时间 | 仅工作日 9:00-18:00 |
| 熔断 | 连续 3 次错误 → 24h 冷却 |
| 反检测 | `disable-blink-features=AutomationControlled` + navigator.webdriver 覆写 |

## 本地文件结构

```
~/my_quant_system/case_library/
├── collect_csrc.py    # 采集脚本（Selenium列表 + HTTP详情）
├── screener.py        # 两层筛选引擎（粗筛+LLM精筛prompt）
├── pipeline.py        # 编排脚本（采集→筛选→入库一条命令）
├── db.py              # SQLite访问层（CaseDB类）
├── schema.sql         # 6表+2FTS+3视图
├── case_library.db    # SQLite数据库
├── raw_html/          # 原始HTML留档
├── raw_text/          # 清洗后纯文本
├── discovered_urls.csv
├── screened_candidates.csv
├── filtered_out.csv
└── collect.log / pipeline.log
```

## 使用流程

```bash
# 1. 仅发现 URL（不下载，安全）
python pipeline.py --discover-only --pages 1

# 2. 全量采集+粗筛+入库
python pipeline.py --pages 1

# 3. LLM 精筛（在 Hermes Agent 中运行）
python pipeline.py --fine-only
# 然后在 Hermes 中说："对 screener 的精筛候选做 LLM 评估"

# 4. 查询分析
python -c "from db import CaseDB; db=CaseDB(); print(db.stats())"
```

## 数据库查询示例

```python
from db import CaseDB
db = CaseDB()

# 全文搜索手法
db.search_by_method("涨停板撤单")

# 多条件筛选
db.filter_cases(violation_type="market_manipulation", year_from="2020", min_penalty=100)

# 导出为 LLM 知识库
db.export_case_markdown("CSRC_2021_0001")
db.export_all_markdown()  # 批量导出
```

## 已知限制

1. **列表页需要 Selenium**（JS渲染），Chrome/chromedriver 需要预先安装
2. **Python 执行路径**：macOS沙箱下需用 `~/.hermes/python-standalone/cpython-3.11.15-macos-aarch64-none/bin/python3`，脚本放 `~/.hermes/scripts/`，`workdir=/Users/yellow/.hermes`
3. **独立Python安装依赖**：`pip install --break-system-packages beautifulsoup4 lxml selenium`（uv管理需加flag）
4. **SQLite FTS5 中文分词**：默认逐字分词，对标签/关键词匹配已够用；如需精细中文搜索可引入 jieba
5. **CSRC 网站可能改版**：CSS selector 和 URL 模式可能需要更新
6. **筛选阈值校准**：22分可精准区分江勇型短线操纵（27-32分）和余韩型长线操纵（15-20分→LLM精筛捞回）

## 标杆案例

江勇操纵"天山生物"案（〔2021〕76号）——信号评分 ~31.8/36：
- 秒级交易时间线（HH:MM:SS）
- 完整手法链：拉升→封单→撤单→涨停板反向卖出
- 4日序列 + 逐笔成交量 + 账户控制 + 申辩复核攻防
- 存储位置：`raw_text/江勇_天山生物_〔2021〕76号_标杆.txt`
