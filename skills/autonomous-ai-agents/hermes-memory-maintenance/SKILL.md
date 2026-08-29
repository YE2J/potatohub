---
name: hermes-memory-maintenance
description: "Use when 用户要压缩/清理/查看 Hermes 记忆预算(MEMORY/USER PROFILE)或记忆备份。"
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [macos, linux, windows]
metadata:
  hermes:
    tags: [memory, backup, compression, hermes-config, budget]
    category: autonomous-ai-agents
    related_skills: [hermes-memory-providers, review-driven-execution]
---

# Hermes 记忆预算维护

管理 MEMORY（personal notes，上限 4500 字符）与 USER PROFILE（上限 3000 字符）两个常驻记忆预算：备份、审计、压缩、恢复。

## 铁律（用户强制，2026-08-23 确立）

**每次压缩/删除 MEMORY 或 USER PROFILE 内容前，必须先完整备份当前记忆，确认备份成功后才允许执行任何变更。**

1. 导出完整快照到 `~/.hermes/backups/memory/memory_<YYYYMMDD_HHMMSS>.md`（内容 = 系统提示中注入的全部条目原文，逐条列出，含条目编号）
2. 用 `date +%Y%m%d_%H%M%S` 生成时间戳文件名
3. 确认 write_file 返回 verified 后才动 memory 工具
4. 压缩后再写一份 post-compression 快照对照

## 标准流程（PM 模式：方案过目 → 用户确认 → 执行）

1. **备份先行**（见铁律）
2. **审计分类**：每条目分三档
   - 🔴 保留：行为红线、运维命脉（cron ID）、进行中项目的活跃状态
   - 🟡 压缩为指针：细节有兜底（报告/skill），记忆里只留结论+红线+指针
   - 🟢 删除：完全重复，或有文件兜底
3. **验证兜底（关键，防指针悬空）**：压缩为指针前必须实际验证目标存在且含细节
   - skill 兜底：`find ~/.hermes/skills -name SKILL.md | grep <名>` 确认存在，再 grep 关键规则词确认细节真的在里面
   - 报告兜底：`ls` 文件存在
   - 本项目教训：#5 代码评审5维校验压缩为"详见skill review-driven-execution"后 grep 发现 skill 无该定义 → 指针悬空，需补进 skill 或恢复原文
4. **方案过目**：表格列出每条 现状/操作/压缩后/省字符/退路，用户确认后才执行（用户拒绝"先斩后奏"）
5. **执行**：memory 工具批量 operations
6. **压缩后快照 + hindsight_retain**：被压缩条目的完整原文 retain 进 Hindsight（与文件备份形成双保险）

## 记忆工具陷阱

- **批量 all-or-nothing**：memory operations 数组任一条 old_text 不匹配 → 整个批次回滚，零条生效（本次实测：old_text 写"查重"、原文是"查重复"，一字之差导致 10 条全部回滚）。每条 old_text 必须与原文完全一致且唯一；失败后从报错 current_entries 核对原文再重发。
- **"详见skill X"指针悬空**：skill 里没有细节 = 空指针。压缩到 skill 前先 grep 验证；若悬空，把细节补进 skill（长期）或从备份恢复原文。
- **区分条目类型，删除风险不同**：
  - 行为红线（如"单模型模拟多角色→必须MOA/Kanban"）——用户 3 次以上纠正过，删前必须明确提示，让用户在知情下决定
  - 进行中项目的活跃状态（如"待拍板 A/B/C"）——删了丢决策上下文，保留
  - 用户自评"前期不熟悉Hermes导致的画像"类条目（沟通偏好、环境事实）——有兜底可删，但提示每条的兜底位置
- **估算省字符 vs 实际**：方案里的省字符数是估算，实际以 memory 工具返回的 usage 为准。

## 恢复路径

被删除/压缩的原文可从：
- `~/.hermes/backups/memory/memory_<时间戳>.md`（完整快照，含编号）
- Hindsight retain（若有）
- 项目报告 docs/ 与 skill references

## References

- references/memory-compression-2026-08-23.md — 首次压缩实战记录：A+B 合并方案、15 处变更、5维校验指针悬空修复、条目删除清单
