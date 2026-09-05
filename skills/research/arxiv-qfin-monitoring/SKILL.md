---
name: arxiv-qfin-monitoring
description: Use when 运维/排查 arXiv q-fin 论文监控管线（脚本/cron/补跑/批量分级台账）。
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [arxiv, q-fin, cron, monitoring, backfill, triage, intake, paper-library]
    category: research
    related_skills: [paper-intake, arxiv, hermes-cron-pipelines]
---

# arXiv q-fin 论文监控管线运维

运营 `~/paper_library/q-fin/` 论文库的自动化摄入管线：机械脚本下载 → cron agent 分级 → TRIAGE 台账。
与 `paper-intake`（单篇深度处理/skill 化）互补：本 skill 管 **L1 摄入层运维与批量补跑**。

## 相关文件与组件

| 组件 | 路径 | 说明 |
|---|---|---|
| 机械脚本 | `~/.hermes/scripts/arxiv_qfin_daily.py` | 查询 arXiv API→下载 PDF/HTML→转 md→存档→维护 INDEX.md；stdout 输出 NEW_PAPERS=N 清单 |
| cron | job 6921de23673c | 每周六 02:00（`0 2 * * 6`）；deliver=all；prompt 两级筛选分级 |
| 台账 | `~/paper_library/q-fin/TRIAGE.md` | 第一节=评分卡唯一定义；第二节=决策记录表（cron/paper-intake/本 skill 共用，禁止复制定义） |
| 索引 | `~/paper_library/q-fin/INDEX.md` | 脚本 rebuild；published 降序表 |
| 论文 | `~/paper_library/q-fin/<id>/{paper.md,paper.pdf,meta.json}` | paper.md 前 ~45 行为 HTML 导航样板，正文从 ~50 行起 |
| 日志 | `~/.logs/arxiv_qfin.log` | 脚本 stderr 与运行日志 |

## arXiv API 关键事实（2026-09 实测）

- arXiv 每日**约 20:00 UTC（北京次日 04:00）**公告新论文；API `published`=提交时刻（非公告时刻），提交到可检索有数小时滞后
- **日期范围查询是官方推荐、根治窗口错配的姿势**：
  `search_query=cat:q-fin.* AND submittedDate:[YYYYMMDDHHMM TO YYYYMMDDHHMM]`（UTC，URL 编码）
- `sortBy=submittedDate` top-200 对 q-fin.* 覆盖约一个月、每天 1~12 条；**修订版仅 ~10%**——"修订版挤占导致 0 条"是流行误判，先实测分布再下结论
- 公告后运行（04:00 CST 之后）+ 周频错峰 = 降机器人指纹；退避重试应对瞬时 RST，持续 RST 需换出口（IP 级封锁）

## 常用命令

```bash
# 常规（默认 7 天窗口，cron 用）
python3 ~/.hermes/scripts/arxiv_qfin_daily.py
# 补跑最近 N 天
ARXIV_SINCE_DAYS=14 python3 ~/.hermes/scripts/arxiv_qfin_daily.py
# 补跑精确 UTC 下限（回填某日之后全部漏检）
ARXIV_SINCE_DATE=202608200000 python3 ~/.hermes/scripts/arxiv_qfin_daily.py
# 补跑量大时后台+notify；日志 tail ~/.logs/arxiv_qfin.log
```

脚本行为：已存档目录（pdir 存在）自动跳过；网络类错误退避 60/300/900s×3（HTTPError 不重试）；无新论文 stdout 为空（上层 [SILENT]）。

## 单篇漏检修复（<5 篇，勿整窗重跑）

日志里某篇 `PDF 下载失败 ...: HTTP Error 404` 时，不要直接整窗重跑——脚本用 API 给的同一 pdf_url，大概率再 404。正确顺序：

1. **探活各版本**：`curl -s -o /dev/null -w '%{http_code}' https://arxiv.org/pdf/<id>v{N}` 逐个版本试；API 的 `link title="pdf"` 指向**最新版**，新版本刚提交时 PDF 可能尚未生成（404）而旧版（v1）可用。
2. **用脚本自身函数做单篇补录**（不要手写第二套下载/转换逻辑）：
   ```python
   import importlib.util, urllib.parse, json
   spec = importlib.util.spec_from_file_location("aq", "/Users/yellow/.hermes/scripts/arxiv_qfin_daily.py")
   aq = importlib.util.module_from_spec(spec); spec.loader.exec_module(aq)
   url = aq.API + "?" + urllib.parse.urlencode({"id_list": AID, "max_results": 1})
   e = aq.parse_page(aq.http_get(url))[0]
   e["pdf_url"] = f"https://arxiv.org/pdf/{AID}v1"   # 修正为探活通过的版本
   pdir = aq.LIB / AID; pdir.mkdir(parents=True, exist_ok=True)
   (pdir / "paper.pdf").write_bytes(aq.http_get(e["pdf_url"], binary=True))
   md = aq.convert_paper(pdir, e)                      # HTML→md 失败自动 fallback PDF
   e["local"] = {"pdf": str(pdir / "paper.pdf"), "md": str(md)}
   (pdir / "meta.json").write_text(json.dumps(e, ensure_ascii=False, indent=2), encoding="utf-8")
   aq.rebuild_index()
   ```
3. 验证：`grep <id> ~/paper_library/q-fin/INDEX.md` 有行即成功，下次 cron 会正确跳过。

## 批量补跑/分级工作流（>30 篇，2026-09 实测 78 篇）

1. **补跑**：后台执行（+notify），实测 8/20 后 76 篇约 2 分钟
2. **切分清单**：`read INDEX.md` 现读后按行均分给 worker（**勿凭日期记忆切分**——实测漏过 2 篇 8/31 published 但 2609 前缀的论文）；每个 worker 拿到精确 ID 清单
3. **worker 指令要点**：逐篇 read meta.json 摘要初筛；疑似 A/B 才 read paper.md 120+80 行；诚实纪律（每篇真实读过才判级、缺失标 ⚠️）；输出 markdown 分级表（日期/ID/标题≤35字/评级/一句话理由+处置）+A/B 沉淀要点+缺失清单；写入草稿文件返回路径（大 summary 会被截断，主会话用 execute_code json.loads 解包）
4. **台账**：决策行**只由主会话统一 append**（防并发写）；状态约定：A/B=⏳ 待拍板、C=⏳ pending（概念卡）、D=✅ archived
5. **校验**：`search_files pattern='^\| 2026-' TRIAGE.md` count == INDEX.md 论文行数

## A 级 skill 化（子代理草稿流程）

1. 子代理精读论文 + skill_view 参考同族 skill 学 frontmatter/正文惯例；要求公式/常数从 paper.md 实际提取、不确定标 ⚠️"论文未给"、SKILL.md 写草稿文件返回路径
2. 主会话 read 草稿审查 → 落盘 `~/.hermes/skills/<category>/<name>/SKILL.md`（cp 即可：skill 系统为文件系统+frontmatter 驱动）→ `skill_view(name)` 验证 readiness_status=available
3. description 首 57 字符内自包含触发句；正文中文、步骤化、含 A股数据源映射/验证方法/陷阱；HTML→md 公式损坏处须对照本地 paper.pdf 并标 ⚠️

## Pitfalls（实测踩坑）

1. **24h 滚动窗口 vs 公告时点错配 = 系统性 0 条**：API 一直返回满页但窗口内 0 条连续多日，先怀疑窗口/时点（修复版已根治：日期范围查询+公告后运行），不要臆断修订版挤占。
2. **公式转换损坏**：arXiv HTML 转 md 丢符号/错量纲（实测：MEM 平稳性约束 ">0" 实为 "<1"；Berkowitz 截断点量纲错）——引用公式前对照 paper.pdf。
3. **并发写台账**：分级 worker 只产出，append 归主会话。
4. **误把评分当盈利概率**：评级/skill 是统计支持强度；论文自身真实市场预注册常为 null，不得建立"分≥X 就实盘"规则（见 minerva-backtest-robustness skill）。
5. **分级周批量用两级筛选**：每篇深读在 30+ 篇时 token 爆炸；meta.json 摘要初筛→疑似 A/B 才深读。
6. **多版本论文 PDF 404 ≠ 论文不可得**：API 的 pdf link 指向最新版，新版本（v2+）提交后 PDF 生成有滞后，此时旧版（v1）常仍 200。先 curl 逐个版本探活再判死刑——HTTPError 脚本不重试，会整篇误判跳过（见上文"单篇漏检修复"）。

## 2026-09-04 关键变更（修复归档）

- 旧版 bug：sortBy=submittedDate top-200 + 本地 24h 过滤，每日 03:10 CST（比公告早 50 分钟）→ 08-24~09-03 连续 11 天 0 条
- 修复：日期范围查询 + 退避重试 + 默认 7 天窗口 + cron 改周六 02:00 + prompt 两级筛选
- 详见 `references/arxiv-monitor-batch-ops.md`（完整诊断数字、78 篇批量分级操作、产出 skill 清单）
