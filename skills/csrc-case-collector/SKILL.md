---
name: csrc-case-collector
description: 从证监会网站采集操纵证券市场行政处罚决定书，两层筛选(信号评分+LLM精筛)，SQLite本地入库。目标：找到江勇案级别的高质量详案。
version: 1.0.0
category: data-science
metadata:
  hermes:
    tags: [csrc, 行政处罚, 操纵市场, 采集, 筛选, 量化研究]
    related_skills: [a-share-research, tushare-data]
---

# CSRC 操纵市场案例采集系统

自动化采集中国证监会行政处罚决定书，重点筛选"江勇操纵天山生物案"级别的高质量操纵市场详案。

## 触发条件

- 用户提到"证监会处罚""操纵市场案例""CSRC case""行政处罚采集"
- 用户需要收集A股违法案例做研究分析

## 系统架构

```
web_search(发现URL) → web_extract(下载) → screener.py(粗筛) → LLM(精筛) → CaseDB(入库)
```

## 核心设计原则

1. **代码能做的不调LLM** — 90%工作在Python层完成，零Token
2. **安全第一，速度不重要** — 政府网站，宁慢勿快
3. **两层筛选漏斗** — 粗筛淘汰80-90%，精筛只处理候选

## 依赖与路径

- Python: `~/.hermes/python-standalone/cpython-3.11.15-macos-aarch64-none/bin/python3`
- 代码: `~/my_quant_system/case_library/`
- 数据库: `~/my_quant_system/case_library/case_library.db`
- pip: 需加 `--break-system-packages`（uv管理环境）
- macOS sandbox: 脚本放 `~/.hermes/scripts/`，数据可读写 `~/my_quant_system/`

## 已验证的CSRC网站结构

**正确URL模式**：
- 列表页: `http://www.csrc.gov.cn/csrc/c101925/zfxxgk_zdgk.shtml?channelid=29ae08ca97d44d6ea365874aa02d44f6` (JS渲染，需Selenium或替代)
- 详情页: `http://www.csrc.gov.cn/csrc/c101928/c{ID}/content.shtml` (纯HTML，web_extract可用)
- 正文选择器: `div.detail-news`

**豆包方案的URL是错的** — `zfxxgk_zdlist_{page}.shtml` 不存在。

### ⚠️ CSRC HTML 格式特点：`<br>` 换行问题

CSRC 详情页大量使用 `<br>` 标签而非 `<p>` 段落标签来排版。这导致 text 提取后每行被分割成独立"句子"，**句均字数严重偏低**（通常 7-12 字符/句）。

**实际影响**（2026-06-23 批次实测）：
| 案例 | 原文长度 | 句均字数 | 筛选结果 |
|------|---------|:--------:|:--------:|
| 冯越峰操纵案 | 6165 字 | ~7 字 | ❌ 句均过低 |
| 朱泽宇操纵案 | 3243 字 | ~8 字 | ❌ 句均过低 |
| 余韩操纵案 | 1919 字 | ~9 字 | ❌ 句均过低 |
| 翟春妮(北京局)案 | 1406 字 | ~12 字 | ❌ 字数+句均双低 |
| ✅ 李鹏案 | 3162 字 | ~54 字 | ✅ 通过（使用 `<p>` 分段）|

李鹏案通过是因为该页面使用了标准的 `<p>` 段落格式。据此推测 CSRC 不同年份/不同撰写人的页面格式不统一。

**应对策略**（推荐优先顺序）：
1. **短方案**：在 `screener.py` 中对 CSRC 来源降低"句均字数"硬门槛（从 15→5），避免误杀
2. **中方案**：在文本提取后做 post-processing：将 `<br>` 换行符替换为空格合并短行
3. **长方案**：在 `collect_csrc.py` 中提取时使用 HTML-aware 解析（保留 `<p>` 结构）

## 收集策略（安全优先）

| 维度 | 策略 |
|------|------|
| 发现URL | `web_search` site:csrc.gov.cn（不消耗本地IP） |
| 下载详情 | `web_extract`（Hermes内置，已验证可行） |
| 备选 | GitHub有Selenium爬虫 goldluo126/718bb567 |
| 频率 | 详情≥5s间隔，单次≤200篇，≤2小时 |
| 熔断 | 连续3次403/超时 → 24h冷却 |

## 筛选体系（9信号评分）

目标标杆: 江勇操纵天山生物案〔2021〕76号 — 秒级时间线、拉升→封单→撤单→涨停板出货、4日序列、完整申辩复核

| 信号 | 权重 | 检测方式 |
|------|:---:|------|
| 秒级时间戳 `HH:MM:SS` | 5.0 | 正则 |
| 时间戳密度 ≥2/千字 | 1.5 | 计数 |
| 手法拆解(拉升/封单/撤单/出货) | 4.0 | 关键词 |
| 申辩复核攻防 | 4.0 | 关键词组合 |
| 账户控制细节 | 3.5 | 关键词 |
| 成交量/金额明细 | 3.0 | 正则 |
| 多日序列(≥3天) | 3.0 | 正则 |
| 结构完整性 | 1.5 | 关键词计数 |
| 字数梯度 | ~0-10 | min(len/8000,1)×10 |

**粗筛阈值: 21** (满分~35.5)。低于阈值的案例在LLM精筛层可能被捞回。

**关键校准发现**: 长线持仓操纵(如余韩案,1252交易日)缺乏秒级时间戳，评分偏低但仍是好案→由LLM精筛补充。

## 文件清单

| 文件 | 用途 |
|------|------|
| `collect_csrc.py` | 采集脚本（requests下载+Selenium发现） |
| `screener.py` | 两层筛选引擎（9信号评分，阈值21） |
| `pipeline.py` | 编排管线（采集→粗筛→入库） |
| `db.py` | CaseDB Python API（contextmanager pattern） |
| `schema.sql` | SQLite DDL (6表+2FTS+3视图) |
| `case_library.db` | 案例库（已验证入库，首条CSRC_2024_0001） |
| `discovered_urls.csv` | URL去重缓存（自动维护） |
| `collect.log` / `pipeline.log` | 运行日志 |

**外部辅助脚本：**

| 路径 | 用途 |
|------|------|
| `~/.hermes/scripts/csrc_pipeline.sh` | cron wrapper：接收URL文件→下载→筛选→入库→统计 |

## Cron自动化

**Cron job:** `CSRC 案例自动采集` (job_id: 2e89791a416c)
**定时:** 每天 8:00（盘前）
**模式:** Agent模式 (`no_agent=false`)，不直接用脚本

### 运行架构

```
Cron Agent (no_agent=false)
  ├─ web_search → 发现新URL（替代Selenium列表页，因为Chrome未安装）
  ├─ 写入 /tmp/csrc_new_urls_YYYYMMDD.txt
  ├─ bash ~/.hermes/scripts/csrc_pipeline.sh <urls_file>
  │     ├─ collect_csrc.py --urls → requests下载详情页
  │     ├─ pipeline.py --screen-only → screener粗筛
  │     ├─ pipeline.py → 入库（CaseDB）
  │     └─ 统计报告
  └─ 汇报结果给用户
```

### 要点

- **Selenium不可用**（Chrome未安装）→ URL发现必须依赖Agent工具的`web_search`，不能直接跑`collect_csrc.py`（它默认调`discover_urls_selenium()`）
- `collect_csrc.py`的`discover_urls_from_search()`备选方案是stub（空函数），不用
- cron用`--urls`参数绕过列表页：`$PYTHON collect_csrc.py --urls /tmp/urls.txt`
- 每篇下载间隔≥5s，单次≤20篇，连续3错误熔断24h

## CaseDB 快速参考

```python
from db import CaseDB, generate_case_id
db = CaseDB()
db.init_schema()

# 插入案例
db.insert_case({"case_id": case_id, "source": "csrc", ...})
db.add_tag(case_id, "涨停板撤单", "method")
db.save_llm_extraction(case_id, {"core_methods": "...", ...})

# 查询
db.search_by_method("涨停板撤单")      # FTS全文搜索
db.filter_cases(violation_type="market_manipulation", year_from="2024")
db.yearly_stats()                      # 年度统计
db.export_case_markdown(case_id)       # 导出Markdown→LLM知识库
db.url_exists(url)                     # 去重检查
```

## 常见问题

**Python import 失败 PermissionError**: macOS TCC沙箱限制。脚本放 `~/.hermes/scripts/`，用 standalone Python 执行。

**screener.py 语法错误**: read_file 读取时 bash error 行混入文件。用过滤脚本去除 `/bin/bash` 和 `shell-init` 行。

**pip install 失败 "externally managed"**: 加 `--break-system-packages`。

**Selenium 不可用**: Chrome未安装，Selenium完全无法使用。不要调`collect_csrc.py`的默认模式（它调`discover_urls_selenium()`会静默返回空）。替代方案：
  - Agent交互模式：`web_search` + `web_extract`（Hermes工具，已验证可行）
  - Cron模式：Agent cron用`web_search`发现URL→写入文件→`collect_csrc.py --urls`下载详情

**Cron运行失败**: 检查`collect_csrc.py`是否用了`--urls`参数。不加--urls会走Selenium路径→返回空→无新案例→报告为空。

**pipeline.sh 最终统计查询报错**: 脚本中最终统计查询使用了 `score` 字段名，但 `cases` 表的实际字段是 `quality_score`。修复方法：编辑 `~/.hermes/scripts/csrc_pipeline.sh` 第 52 行的 `score` → `quality_score`。

**真实 yield 参考**（2026-06-23 批次）: 9 个 URL 下载成功，粗筛通过 1 篇（李鹏案），实际 yield ≈ 11%。但由于 CSRC `<br>` 格式问题，大量应有价值的案例被误杀。排除格式因素后预期 yield 约为 30-40%。

**discovered_urls.csv 首次为空**: cron首次运行时没有缓存，所有搜索到的URL都会被下载。后续运行自动去重。

**阈值校准**: 标杆案(江勇)~27分，中档案(刘洪涛)~21分，简短案(夏德全)~7分。阈值21分可捕获大多数有申辩复核的操纵案。严格模式保持22分，松散用20分。
