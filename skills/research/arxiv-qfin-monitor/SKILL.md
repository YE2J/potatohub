---
name: arxiv-qfin-monitor
description: Use when 运维/修复 arXiv q-fin 论文监控：漏检诊断、补跑、台账一致性。
author: Hermes Agent
version: "1.0.0"
license: MIT
metadata:
  hermes:
    tags: [arxiv, q-fin, cron, monitoring, paper-library, backfill, ops]
    category: research
    related_skills: [paper-intake, llm-wiki]
---

# arxiv-qfin-monitor — arXiv q-fin 论文采集/监控管道运维

> 本文档负责「采集层 + 调度层」：机械脚本、cron、补跑、漏检诊断、台账一致性。
> 论文抓下来之后的深处理（精读→PoC→建 skill）走 `paper-intake`（TRIAGE 流程）。

## When to Use
- 用户问"arXiv 论文监控有更新吗 / 为什么没收到推送"——先查采集层健康，再谈论文内容
- 修复/改调度/补跑漏检论文 / 校验 paper_library 台账一致性
- 新增类似外部源监控管道时参考本管道结构

## 管道结构（2026-09-04 修复后基线）

| 组件 | 位置 | 说明 |
|---|---|---|
| 机械脚本 | `~/.hermes/scripts/arxiv_qfin_daily.py` | 查询→下载→markitdown 转 md→存档→维护 INDEX；stdout 输出 `NEW_PAPERS=N` 清单供 cron agent 分级 |
| cron | 6921de23673c，每周六 02:00 CST（`0 2 * * 6`） | 脚本输出注入 agent prompt；agent 按 TRIAGE.md 分级、写台账、A/B 推送 / C/D 或空则 `[SILENT]` |
| 论文库 | `~/paper_library/q-fin/<arxiv_id>/` | paper.pdf / paper.md / meta.json（meta.json 与脚本产出格式一致） |
| 台账 | `~/paper_library/q-fin/TRIAGE.md` | 评分卡唯一定义 + 决策记录（86 行基线）；cron 与 paper-intake 共用 |
| 索引 | `~/paper_library/q-fin/INDEX.md` | 脚本 rebuild；表头 `| 发布日期(UTC) | arXiv ID | 标题 | 子分类 | 链接 |` |
| 日志 | `~/.logs/arxiv_qfin.log` | 每轮追加：查询范围/API 返回条数/窗口内条数/逐篇处理 |

## 关键事实：arXiv API 时间语义（实测，曾致连续 11 天静默漏检）

1. arXiv 每日**约 20:00 UTC**（北京 04:00）公告新论文；API `published` ≈ 提交时间，论文在公告后才可检索。
2. `sortBy=submittedDate` top-200 覆盖**近一个月**（32 天 ~200 篇）；修订版（updated≠published）仅 ~10%——**不会**把新公告挤出 200（"修订版挤占"假说已被实测证伪）。
3. 因此**本地滚动窗口 + 早于公告的运行时刻 = 整批错过**：旧脚本 03:10 CST（比公告早 50 分钟）+24h 窗口 → 连续 11 天"API 返回 200 条但窗口内 0 条"，漏 76 篇。
4. 官方推荐查询是**日期范围**（服务端过滤）：
   `search_query=cat:q-fin.* AND submittedDate:[YYYYMMDDHHMM TO YYYYMMDDHHMM]`（UTC）。上限放宽 +1 天容差；本地仅做去重不做窗口过滤。

## 运维 Runbook

### 例行健康检查（用户问"有更新吗"时）
1. `cronjob_manage list` 找 6921de23673c：last_status / last_run_at / last_fire_error。
2. `tail ~/.logs/arxiv_qfin.log`：确认最近一次"API 返回 N 条, 窗口内 M 条"，M>0 或为空属正常；连续 0 条 + 窗口=7 天 = 异常信号。
3. `~/paper_library/q-fin/INDEX.md` 首行日期距今 >7 天且非周末/假期 → 疑似漏检，进入诊断。
4. 台账一致性：`grep -c '^| 2026-' TRIAGE.md` 应等于 INDEX 行数（本文档基线 86=86）。

### 补跑（抓回历史漏检）
```bash
cd ~ && ARXIV_SINCE_DATE=YYYYMMDDHHMM /usr/bin/python3 ~/.hermes/scripts/arxiv_qfin_daily.py
```
- 脚本按存档目录存在自动去重跳过；补跑完成后 INDEX 自动 rebuild。
- 补跑量大时后台跑：`ARXIV_SINCE_DATE=202608200000 ... > /tmp/arxiv_backfill_$(date +%Y%m%d).log 2>&1`。

### 冒烟测试（改脚本后必做）
小范围跑通再大补跑：`ARXIV_SINCE_DATE=<近 2 小时前> ` 应返回 0~2 条并完成下载转换；确认日期范围语法有效（语法错会返回 0 条或错误）。

### 分级批量处理（补跑量大时）
- 主会话先算待分级清单（INDEX − 台账 diff），按 published 日期段均分并行 delegate（每个附精确 ID 清单）。
- 台账由主会话统一追加（防并发写冲突），日期列取 meta published 前 10 字符。
- A/B 处置等用户拍板后改 ✅ done；C=概念卡 ⏳ pending；D=仅存档 ✅ archived。

## Pitfalls

1. **静默漏检三特征**：API 一直可达（返回 200 条）、窗口内 0 条、连读日志时间戳——先查运行时刻 vs arXiv 公告时点，再查窗口覆盖。
2. **诊断先实测后猜测**：dump 返回条目的 published 时间分布（哪些日期、修订占比）再定根因；勿凭现象套"挤占/封锁"假说。
3. **整点固定高频查询像机器人**：会触发出口 IP 层重置（arXiv 状态页正常、全部边缘 IP 即时 RST、example.com 基线正常）。缓解：降频（日→周）、错峰、网络错误退避重试 60s/300s/900s ×3（仅网络层错误；HTTPError 不重试）。
4. **改调度同步改 prompt 里所有时间词**：cron prompt 自包含，漏改会前后矛盾（日更文本+周更调度）。
5. **paper.md 是 arXiv HTML 导出**：前 ~45 行导航样板，正文从 ~50 行起；HTML→md 会损坏个别公式（方向符号、量纲），引用前对照本地 paper.pdf。
6. **补跑后校验闭环**：按 published 日分组计数与 INDEX 对（跨 ID 前缀 2608/2609 的日期段易漏分）；最终 grep 台账计数 == INDEX 行数。
7. 分级/增强委托产出的 **patch 锚点常带说明文字与代码围栏**——old_string 必须取围栏内目标文件字面行；增量正文若被 ```markdown 包裹先剥首尾；批量 patch 后 grep 特征词验证命中。

## 相关文件
- 详细 API 语义与 2026-09-04 事故复盘：`references/arxiv-api-notes.md`
- 深处理流程/评分卡：`paper-intake` skill（`~/paper_library/q-fin/TRIAGE.md`）
- 运维坑速查（wiki）：`~/.hermes/wiki/Hermes/运维避坑.md`「arXiv 论文源」小节
