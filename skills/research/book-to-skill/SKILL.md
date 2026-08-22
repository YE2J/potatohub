---
name: book-to-skill
description: "Use when 用户要下载/学习电子书。全流程：下载→转md→入库→汇报→确认→笔记+skill。"
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [macos, linux]
metadata:
  hermes:
    tags: [ebook, zlibrary, markdown, skill-extraction, learning]
    category: research
    related_skills: [office-to-markdown, ocr-and-documents]
---

# Book → Skill 电子书学习工作流

把电子书从下载到沉淀为可复用技能的全流程编排。**编排现有能力，不重复造轮子**：
下载用 `mcp_zlibrary_*` 工具，转 md 走 `office-to-markdown` 决策路由，入库进
`~/book_library/`，产物是「学习笔记 + 领域操作 skill」。

## 触发条件

- 用户说「下载/找/搜一本书」「学习这本书」「把这本书变成 skill」
- 用户给出书名、作者、主题、ISBN 之一

## 流程总览（6 步）

```
① 搜索选书 → ② 下载 → ③ 转 md → ④ 入库 book_library → ⑤ 汇报 → ⑥ 确认后产物
```

## 步骤 1 — 搜索选书

用 `mcp_zlibrary_search_books`（或 `search_by_author` / `search_advanced`）搜索：

```
mcp_zlibrary_search_books(query="<书名或关键词>", limit=5)
```

返回结果含 id/name/author/year/language/extension/size。**给用户列候选表**
（书名/作者/年份/格式/大小），让用户确认选哪本，不要自作主张下载。

⚠️ 若 zlibrary 搜索失败（凭据/网络/镜像问题）：
- `ZLIBRARY_MIRROR` 指向不可达镜像 → 换可用镜像（用户在浏览器验证过 z-lib.li）
- 或 `mcp_zlibrary_search_multi_source` 走 LibGen/Anna's Archive

## 步骤 2 — 下载

格式优先级（用户约定 2026-08-22）：**epub > pdf > txt**。

```
mcp_zlibrary_download_book_to_file(book=<搜索结果中的book对象>, download_dir="~/book_library/<书名>_download/")
```

- 下载目录先建 `~/book_library/<书名>/` 的临时子目录或直接下到书目录
- 下载后验证文件存在且非空（`ls -la` + `file` 确认类型）

## 步骤 3 — 转 md（按格式分流）

加载 `office-to-markdown` skill 并按决策路由执行：

| 格式 | 工具 | 说明 |
|---|---|---|
| epub | markitdown | 直接支持，XML 文本提取 |
| pdf（文本可选） | markitdown → pymupdf 回退 | markitdown PDF 表格会切碎词条，列表型/词条型用 pymupdf 文本层 |
| pdf（扫描件） | MinerU OCR | `env -u PYTHONPATH ~/.mineru-venv/bin/mineru -p in.pdf -o out -m ocr -b pipeline` |
| txt | 直接读/cp | 无需转换 |

```bash
MD="/Users/yellow/.hermes/hermes-agent/venv/bin/python"
"$MD" -m markitdown "输入.epub" > "输出.md"   # epub/pdf 走这个
```

- 转换后验证：`wc -l -w -c 输出.md` + `grep -E "^#{1,3} "` 看章节大纲
- **图片处理**：≤10 张 → 自动 vision_analyze 全量分析；>10 张 → 列清单让用户挑。
  docx 内的 P-mode 透明 PNG 要先垫白底（详见 office-to-markdown 步骤 2.5）。
- 书籍图片通常是插图/封面/图表，多数情况列为「图表索引」即可，不必每张深读；
  数学/量化类书的公式图表要重点分析（用户学习高数+量化）。

## 步骤 4 — 入库 book_library

目录结构（用户约定 2026-08-22，独立于 doc_library）：

```
~/book_library/<书名>/
├── <书名>.<原格式>        # 原文件
├── <书名>.md              # 转换产物
├── <书名>.note.md         # 学习笔记（步骤6a 生成后放这）
├── images/                # 提取的图片
└── meta.json              # 元数据（来源/日期/格式/页数）
```

- 建目录：`mkdir -p ~/book_library/<书名>/images`
- 移动原文件 + md + 图片到对应位置
- 写 `meta.json`：`{"title": "", "author": "", "format": "", "pages": 0, "downloaded_at": "", "source": "zlibrary", "converted_by": "markitdown|pymupdf|mineru", "image_count": 0}`
- **更新 INDEX.md**：用专用脚本（幂等，勿 echo >> 追加破坏表格）：
  ```bash
  python3 ~/.hermes/scripts/update_book_library_index.py \
    --title "<书名>" --author "<作者>" --format epub \
    --status "待学习" --date 2026-08-22 --dir "<书名>"
  ```
  （若脚本不存在，先写它：逻辑仿照 update_doc_library_index.py，按书名匹配既有行替换/插入）

## 步骤 5 — 汇报（供用户决策是否学习）

汇报格式见 `references/book-report-template.md`。核心三要素（用户约定）：
1. **目录大纲**：`grep -E "^#{1,3} "` 提取的章节结构
2. **核心要点**：3-6 条本书最值得学的知识点（从正文抽样读取，不要整本读完）
3. **难度/相关性评估表**：难度（入门/进阶/专家）、与用户当前学习方向（量化/高数）的相关性、预估学习时间

**省 token 纪律**：这一步只读大纲 + 抽样关键章节（每章标题 + 开头段），
不要全量读 md 进上下文。读完汇报，**等用户决策**。

## 步骤 6 — 确认后的产物

用户回复「学/学习/要」→ 执行 6a；回复「提炼/生成 skill」→ 执行 6b；两者都要 → 都执行。

### 6a 学习笔记（先做）

按 `references/note-template.md` 生成 `<书名>.note.md`，写入书目录，更新 INDEX.md 状态为「学习中/已学习」。

### 6b 领域操作 skill（确认后提炼）

按 `references/skill-extraction-guide.md` 提炼。要点：
- 把书本的**可操作知识**（流程/方法/公式/规则）转成 SKILL.md，不是全书摘要
- 命名：`<领域>-<核心动作>`（如 `quant-factor-ranking`）
- 写完后用 `skill_view` 自查格式（frontmatter 必须有 name/description/version）
- 引用来源：SKILL.md 中注明「提炼自《书名》+ 章节」

## 验证（收尾必做）

| 检查项 | 命令 |
|---|---|
| 转换产物完整 | `wc -l -w -c <书名>.md`，章节标题数合理 |
| 原文件存在 | `ls -la ~/book_library/<书名>/` |
| 入库完成 | `grep "<书名>" ~/book_library/INDEX.md` |
| skill 可用 | `skill_view(name="<新skill名>")` 返回正常 |
| 笔记生成 | `ls ~/book_library/<书名>/*.note.md` |

## Pitfalls

- **下载不自动选书**：搜索结果列候选表让用户挑，下载是用户决策后的动作
- **markitdown PDF 表格切碎**：词条/列表型 PDF 直接用 pymupdf 文本层
- **MinerU 必须 env -u PYTHONPATH**：Hermes 会话注入的 PYTHONPATH 会破坏其依赖解析
- **INDEX.md 用脚本更新**：echo >> 会破坏表格结构，整体 write_file 会抹掉手动内容
- **epub 的图片是内嵌 data URI**：markitdown 会 base64 内联，`grep -v "data:image"` 可去掉
- **不要整本读入上下文**：300KB md ≈ 80k tokens，按章读 + 抽样，省 token 纪律
- **学习笔记 ≠ skill**：笔记是给用户看的理解存档，skill 是可复用操作流程，两者都要但别混写
- **书本可能有版权**：仅用于个人学习研究，入库不对外分发（用户自担合规风险）
