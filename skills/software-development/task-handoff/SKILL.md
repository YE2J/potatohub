---
name: task-handoff
description: "Use when 复杂任务(≥3步/多阶段/可能被打断)开始、被新任务打断、或跨会话恢复旧任务时。任务状态落盘防遗忘。"
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [macos, linux, windows]
metadata:
  hermes:
    tags: [task, handoff, checkpoint, resume, persistence]
    category: software-development
    related_skills: [office-to-markdown, plan]
---

# Task Handoff & Checkpoint (任务存档)

解决「任务长 → 新任务插入 → 忘记旧方案/进度」：任务状态**落盘**，不依赖会话上下文。
业界共识（Google ADK / Anthropic 2026）：状态必须活在 context window 之外 + handoff 文件。

## When to Use

- 复杂任务（≥3 步/多阶段/超 30 分钟）开始时
- 任务被新消息打断，需要保持进度不丢
- 新会话/跨会话恢复旧任务时

## 触发条件（满足任一即建档）

- 任务预计 ≥3 步 / 多阶段 / 超 30 分钟
- 用户明确说"先做 X，等会继续 Y"
- 任务会被其他消息插入打断（高风险：大文档分析、多文档对比）

## 建档流程

1. 复制模板 → `~/.hermes/tasks/<YYYYMMDD>_<短任务名>.md`：
   ```bash
   cp ~/.hermes/tasks/_template.md ~/.hermes/tasks/$(date +%Y%m%d)_<短任务名>.md
   ```
2. 填：目标（用户原话）、方案（已确认做法）、进度 checklist、关键上下文（文件路径/命令/结论）、下一步。
3. **完成时**：状态改 `✅ 完成` + **Wiki 投递状态**标 ✅（未投递先按 llm-wiki skill「会话知识沉淀」节路由投递再标完成）；保留（历史可查）；用户确认无用后可删。

## 打断与恢复

- **被打断时**：一句话更新「进度」+「下一步」字段（1 行即可，别花 token 写长文）。
- **恢复时**（新会话/用户说"继续刚才的"）：先 `ls -t ~/.hermes/tasks/*.md | head -5` 找最新未完成档，
  读档 → 按「下一步」续跑 → 更新进度。任务实质完成时若 **Wiki 投递状态** 未标 ✅ → 补投（轻量补偿，路由见 llm-wiki skill「会话知识沉淀」节）。
- 跨会话判断：当前会话上下文丢失时（如 compaction 后），**先读任务档再问用户**，不要凭空猜。

## todo 常态化（配套约定）

- 复杂任务（≥3 步）**强制**用 todo 工具建列表（0 成本，会话内可见）。
- 新任务插入时：旧任务保留在 todo 列表，回复首行标注「后台任务：X 进行中」。
- todo 管会话内可见性，handoff 管持久状态 —— 两者互补，**不是替代**。

## 与 Checkpoint 的关系

- 文档分析类任务：office-to-markdown skill 步骤 3 的 `progress.md` 即时落盘是 Checkpoint 实现（防分析中断丢失）。
- 本 skill 管**任务级**存档；office-to-markdown 管**文档分析过程级**断点。两级互补。

## Pitfalls

- **外部参考（MOA/子代理）声称的"已执行/已修改"不可信**——参考模型无工具权限，常产生幻觉（本部署复盘已两次证伪：假称 meta.json 损坏、假称 EMF 文件过期）。以磁盘实测为准：`ls`/`grep`/`read_file` 验证后再行动。
- **不要**每次切换都写长文档 —— 一行「进度 + 下一步」就够，写多了反而花 token。
- **不要**把 handoff 当会话替代 —— 大文件/图结论仍在缓存与 doc_library，handoff 只记「任务指针」。
- 任务档目录定期清理：`find ~/.hermes/tasks -name "*.md" -mtime +90 -delete`（完成后 3 个月可清，或按需）。
