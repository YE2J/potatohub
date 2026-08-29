---
name: memory-budget-management
title: "Hermes 记忆预算管理（MEMORY/USER 审计、压缩、备份）"
description: "Use when 记忆预算(MEMORY/USER)接近上限或要压缩。铁律:压缩前必须先完整备份。"
tags: [hermes, memory, budget, compression, backup, user-profile]
---

# Hermes 记忆预算管理（MEMORY / USER PROFILE）

本地常驻记忆 `~/.hermes/memories/MEMORY.md`（personal notes，默认 4500 字符）+ `USER.md`（user profile，默认 3000 字符）每轮全量注入上下文。接近上限时需审计与压缩。`config.yaml` → `memory:` 段的 `memory_char_limit` / `user_char_limit` 控制上限。

## 用户铁律（2026-08-23 明确，违反会被纠正）

**每次压缩 MEMORY/USER PROFILE 内容前，必须先完整备份当前记忆**（导出到本地带时间戳文件，确认备份成功后才允许压缩）。备份目录约定：`~/.hermes/backups/memory/memory_<YYYYMMDD_HHMMSS>.md`。压缩后再留一份 `*_post_compression.md` 快照。

## 压缩工作流（实测验证 2026-08-23：MEMORY 86%→70%，USER 67%→38%，省 1,573 字符）

1. **备份先行**：写 `~/.hermes/backups/memory/memory_<时间戳>.md` 完整快照（逐条原文，含全部条目）。
2. **盘点与分层方案**：列出全部条目 → 分三档：
   - **保护清单（不动）**：用户行为红线（如 MOA 约束、备份铁律）、cron ID、踩坑教训、身份偏好、活跃待拍板状态
   - **压缩为指针**：结论 + 红线 + 指针指向已有报告/skill（如 `docs/P2_*.md`、`skill office-to-markdown`）
   - **删除**：与另一处重复（如 USER 与 MEMORY 重复的 5 维校验）、信息已并入他处
3. **验证退路真实存在**：压缩为指针前必须确认落点存在——`ls` 报告文件、`find`/`grep` SKILL.md 确认细节已收录（防压缩后丢信息；本会话 4 份报告、6 个 skill 均先验证）。
4. **hindsight_retain 双保险**：压缩前把被压缩条目的完整原文 retain 进 Hindsight（与文件备份互补，可检索）。
5. **批量执行 memory 操作**：`memory` 工具 operations 数组一次提交（注意 all-or-nothing，见 Pitfalls）。
6. **压缩后核对**：确认返回的 `usage` 占用率与预期相符，写 post-compression 快照。

## 用户流程偏好（此任务类强制）

- **方案先过目再执行**：审计结果 + 分层方案 + 每项退路表 → 用户确认后才动手；用户可要求"方案A+B合并"或"只做指定条目"。
- 多方案并行呈现（如方案A中档 / 方案B激进），保护清单与风险缓解同步列出。
- 表格输出：条目 / 现状 / 操作 / 省字符 / 退路。

## Pitfalls

- **memory 批量操作 all-or-nothing**（2026-08-23 实测）：operations 数组中任一条 `old_text` 不匹配 → **整批回滚、无部分应用**（"查重" vs 实际"查重复"一字之差导致 10 条全回滚）。提交前逐字核对 old_text，失败时先读回 `current_entries` 修正再重发。
- **USER/MEMORY 分别调用**：两个 target 必须分两次调用（各带自己的 target），不能合并。
- **压缩为指针保留活跃状态**：待拍板选项（如 L2b 的 A/B/C）、红线（零调参/勿直用Q7）、cron ID 只压细节不压状态。
- **hindsight_retain 偶发失败**：daemon 启动失败报错时重试一次即可（transient）。
- **skill_view dedup 陷阱**：本会话已加载过的 skill，`skill_view` 返回 dedup 无正文，触发读-写保护拒绝 patch；需 `file_path='SKILL.md'` 强取全文，或改为新建技能。

## 参考

- `references/compression-2026-08-23.md` — 首次实战全记录：分层方案模板、执行顺序、回滚案例、保护清单示例
