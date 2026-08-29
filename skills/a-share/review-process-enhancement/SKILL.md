---
name: review-process-enhancement
title: "评审流程改进记录"
description: "本会话中实施的评审流程改进：断言声明段、验证命令段、停止假汇总、圆桌讨论模式。作为阶段一交付物存档，供后续阶段参考。"
tags: [review, process, checklist, roundtable]
---

# 评审流程改进 — 阶段一交付物

## 变更汇总

| 变更 | 文件 | 说明 |
|:-----|:-----|:------|
| Persona 5条运行时校验 | `memory(target=user)` | 每次响应生效的类型/路径/权限/单位/日期规则 |
| code-review-checklist skill | `~/.hermes/skills/a-share/code-review-checklist/` | 26项分类检查清单含验证方法 |
| 评审卡断言声明段 + 验证命令段 | `kanban-parallel-review` SKILL.md Step 2 | 4 worker 卡 body 模板全部重写 |
| 停止假汇总 | `kanban-parallel-review` SKILL.md Step 3 | 改为直接输出4份原始报告 |
| kanban_await.py 自动归档 | `~/my_quant_system/scripts/kanban_await.py` | 完成后 `hermes kanban archive` |
| 圆桌讨论模式 | `moa-multi-model-review` SKILL.md | MOA（`/moa <prompt>`）用于多模型圆桌讨论和交叉验证 |

## 5-Agent 圆桌结论（6项改进的实施路线图）

### 阶段一（本周完成）：② + ①
- ② 评审卡模板断言声明段 ✅
- ① code-review-checklist 落地验证 ✅
- ⛔ 停掉无矛盾检测的汇总 ✅

### 阶段二（下周）：③ + ⑤ 并行
- ③ Orchestrator 断言对齐（改造 kanban_await.py，提取4份报告断言做交集/差集/矛盾检测）
- ⑤ 自动验证命令执行简化版（命令白名单 PRAGMA/ls/stat，一键执行）

### 阶段三（本月）：④ + ⑥ 简化版
- ④ 轻量两轮评审（第一轮广度 + 第二轮 GLM+Xiaomi 深度验证疑点）
- ⑥ P0 修复补丁手动触发复核

## 评审模式选择

| 模式 | 用户信号 | 派发方式 | 是否真实多模型 |
|:-----|:---------|:---------|:--------------|
| 独立审查 | "安排4个agent" / "安排4个agent去评审" | 4 张 Kanban 卡 | ✅ 不同模型 |
| 协作讨论 | "一起讨论" / "圆桌" / "辩论" | **MOA（`/moa <prompt>`）** | ✅ 不同模型 + 聚合仲裁 |
| 执行修复 | "修复bug" / "跑脚本" / "查库" | `delegate_task` | ❌ 单模型 |

> ⚠️ **已纠正**：`delegate_task(role=orchestrator)` 一人分饰多角不是真正的多模型讨论。必须用 MOA 或 Kanban 两轮模拟。详细见 `multi-model-orchestration` skill。

references/is_open-type-bug-case-study.md

## 已知故障模式（Xiaomi 统计）


| 排名 | 故障 | 频次 | 验证命令 |
|:----:|:-----|:----:|:---------|
| 1 | 单位/量纲错误 | 5 | SELECT col LIMIT 1 确认数量级 |
| 2 | 跨数据源不匹配 | 4 | ❌ 需增加交叉验证查询 |
| 3 | 类型比较 | 3 | PRAGMA table_info 确认列类型 |
| 4 | 运行时环境 | 3 | ls + stat 确认文件/权限 |
| 5 | 连接泄漏 | 2 | ❌ 需追踪所有 conn 路径 |

## 新增故障模式（2026-08-25 实测）：参考模型编造"实查结果"

| 故障 | 实例 | 防线 |
|:-----|:-----|:-----|
| 参考模型声称已实查的事实（文件损坏/冲突标记/目录内容） | MOA 评审中 Minimax 声称 `多模型军团.md` 含 30+ git 冲突标记、queries/ 有碎片——实查全部为 0，文件干净 | **执行代理必须亲自验证参考模型声称的任何"实查结果"**（grep/read_file/sqlite3），聚合输出前先核验；虚构事实在汇总中标注不实 |

> 含义：评审流程的"验证命令段"不只用于校验数据，也用于**校验参考模型自身的声明**。任何"我查过了，结果 X"都必须可复现——`grep -c` 一行命令就能证伪的声明，不值得信任。
