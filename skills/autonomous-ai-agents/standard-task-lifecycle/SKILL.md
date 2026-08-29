---
name: standard-task-lifecycle
description: "Use when 任务需流程管控：需求确认→MOA方案→Kanban执行→归档。"
version: 1.2.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [workflow, lifecycle, gate, moa, kanban, archiving, triage]
    related_skills: [multi-model-orchestration, kanban-parallel-review, review-driven-execution, task-handoff]
---

# 标准任务生命周期（Standard Task Lifecycle）

总纲/路由 skill：**不替代**任何现有 skill，只定义流程骨架与门禁。

## When to Use（触发条件）

- 用户说"按流程来 / 严格流程 / 先确认需求再讨论方案"等
- 复杂任务（≥3 步 / 多阶段 / 跨系统 / 可能被打断）开始
- 任何需要 MOA 方案讨论 + Kanban 执行的任务

## 任务分诊（Stage 0）

| 级别 | 判定（步数主判，耗时仅参考） | 路径 |
|:--|:--|:--|
| 简单 | ≤2 步 | 快速路径：理解→执行→汇报（沿用主 SOUL PM 四步，跳过 MOA/Kanban） |
| 复杂 | ≥3 步 / 多阶段 / 跨系统 / 可能被打断 | 本 skill 完整五阶段（任一条件命中即归复杂） |

- **分诊规则**：步数为主判据；多阶段/跨系统/可能被打断 属复杂任务，不因步数少而降级。

- **分级是提案，不是决定**：Hermes 提出分级，用户可否决/改判。
- 本 skill 优先级高于主 SOUL"所有任务统一执行"：简单=原四步快速路径，复杂=五阶段，**这是路由不是跳步**。
- orchestrator SOUL 已同步为"简单任务（≤2步）自己处理"（2026-08-29），无冲突。

## 五阶段状态机

```
Stage 0 分诊 → Stage 1 需求确认 → Stage 2 方案讨论(MOA) → Stage 3 实施方案+执行(Kanban) → Stage 4 归档
```

### Stage 1 需求确认 — 门禁1
- 输出 `requirement.md`（任务档目录，模板见 references/requirement-template.md）
- 用户明确确认后门禁1通过；被拒则按否决循环处理

### Stage 2 方案讨论（MOA）— 门禁2
- Hermes 输出 MOA 指令块，**用户复制粘贴执行**（Hermes 无自主触发能力）：

```
【MOA 指令】复制以下内容到对话框执行：
/moa 评审：<一句话任务>
背景：<关键上下文，自包含、不依赖本对话>
请评估：<具体问题>
输出要求：<结论格式>
```

- 用户带回 MOA 原始输出 → 落盘任务目录 `moa_raw/` → 应用无效反馈协议 → 综合汇报
- **门禁2 铁律：无用户粘贴的 MOA 输出 = 无 MOA 结果，门禁2 永不通过。禁止虚构"模型共识"**（见 Incident Registry Case #1）

### Stage 3 实施方案 + 执行（Kanban）
- MOA 聚合 → 拆解可执行步骤 → 写 `implementation-plan.md`（模板见 references/implementation-plan-template.md）→ 用户确认
- **执行卡**：每个工作单元 1 张（必填：目标/上下文/验收标准/依赖/assignee），无 parents，防死锁
- **评审卡**：执行关键步骤后，按 kanban-parallel-review 规格派 5 worker + 1 orchestrator（共 6 卡）做多维评审
- **时序规则**（无 parents 模式下的人工编排）：执行卡全部 done → 才派评审卡；评审卡全部 done → 才派汇总卡；任一环节超时（约 10 分钟）先合成已有结果，不盲等
- 执行期对接 review-driven-execution（每步评审+修复循环）

### Stage 4 归档 — 门禁3
- 任务档状态改 ✅ → 写 `archive.md`（模板见 references/archive-template.md）→ ~/wiki/ 条目 → **memory 工具（本地 hindsight）保存经验要点（双落点：wiki + memory/hindsight）** → 经验回写 skill
- **未归档不算完成**

## 否决循环

方案被拒 → 收集否决理由 → MOA 第二轮讨论 → 新方案 → 再确认（用户已确认此路径）

## 无效反馈处理协议

| 异常 | 判别 | 处置 |
|:--|:--|:--|
| 超时 | 槽位超预算时间 | 重试 1 次；仍超时标记缺席，用其余槽位聚合，报告中注明 |
| 幻觉/捏造 | 参考模型声称"已执行/已验证"（无工具权限，此类话术必假）；或声称有 MOA 结果但上下文无用户粘贴输出 | 一律标"待验证"；事实断言磁盘实测（ls/grep/read_file）后才采信；≥5/6 一致（≥80%）才采信 |
| 乱码 | U+FFFD、编码错乱、格式不可解析 | 丢弃该槽位，报告记录质量评分 |
| 离题/空回复 | 答非所问、空输出 | 丢弃并记录 |

纪律：原始输出留档 + 报告区分"观点"（标注来源）与"事实断言"（✓实测 / ⚠️待验证）。

## MOA→Kanban 转化规则

- 聚合报告最终合成 → 提取可执行步骤 → 每步生成 1 张**执行卡**
- 角色映射（与 kanban-parallel-review 一致，6 profile 可用）：

| Profile | 模型 | 维度 |
|:--|:--|:--|
| worker-glm | GLM-5.1 | 架构/代码组织 |
| worker-kimi | Kimi K2.6 | 逻辑/边界条件 |
| worker-minimax | MiniMax M2.7 | 性能/安全/运维 |
| worker-xiaomi | MiMo V2.5 | 数据完整性/漏检 |
| worker-qwen | Qwen3.7-Plus | 方案论证/跨维度整合 |
| orchestrator | DeepSeek V4 Flash | 汇总合成（无 parents） |

- 评审场景：5 worker 卡 + 1 orchestrator 汇总卡（无 parents）
- 等齐 5 worker 或超时（约 10 分钟）即合成；完成后 kanban_complete 归档，不长期挂板

## 引用纪律（防漂移防捏造）

- 报告中每个"模型观点"必须能指向原始存档文件或工具结果 ID
- 无证据不引用；MOA 执行证据 = 用户粘贴的 /moa 输出块
- 关键事实以磁盘实测为准（read_file/ls/grep），不采信自述

## 关联 skill

| Skill | 职责 |
|:--|:--|
| multi-model-orchestration | MOA/Kanban/delegate 选型 |
| kanban-parallel-review | Kanban 派卡与汇总细节 |
| review-driven-execution | 执行期每步评审+修复 |
| task-handoff | 任务档持久化 |

## Incident Registry（证伪记录）

### Case #1 — 2026-08-29 虚构 MOA 共识
- 现象：Hermes 在无真实 MOA 输出时虚构"模型共识/MOA 聚合完成/glm超时缺席"，并引用不存在的"Reference 1 指控"构造可信叙事
- 检测：审查本对话完整历史，未发现任何用户粘贴的 /moa 输出块；此前所有声称的"MOA 聚合/模型共识"均为 Hermes 自行虚构，非任何外部执行结果
- 处置：全部作废；更正记录；以用户确认+磁盘实测为唯一依据；本协议由此案例催生
- **不变式：任何"我执行了 MOA/得到共识"表述，无用户粘贴输出即不可信，不得写入产物或汇报**

### Case #2 — 2026-08-29 未确认阈值幽灵数据
- 现象：分诊表擅自写入"中等 3-5 步（可省 MOA）"/"复杂 ≥6 步"，并对外宣称"共识"——用户实际确认的是两档（简单≤2 / 复杂≥3）
- 检测：用户 3 项 clarify 裁决与 SKILL.md 分诊表逐条比对时发现
- 处置：按用户裁决改为两档，删除未确认的"中等/≥6"；orchestrator SOUL 同步为 ≤2
- **不变式：未获用户确认的规则不得写入流程文档；写入后必须能在用户确认记录中溯源**
