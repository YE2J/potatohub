---
name: hermes-memory-providers
title: "Hermes 长时记忆 provider 管理（评估/切换/自托管可行性）"
description: "Use when 用户问记忆系统效果、换 memory provider 或考虑自托管记忆服务。"
tags: [hermes, memory, supermemory, hindsight, provider, self-host]
---

# Hermes 长时记忆 Provider 管理

用户常问「记忆系统用得怎么样」「能不能换记忆方案」「自托管记忆服务」。这些操作围绕 `config.yaml` 的 `memory:` 段和 `~/.hermes/hermes-agent/plugins/memory/<name>/` 下的 provider 插件。

## 架构速览

- 配置：`config.yaml` → `memory:` 段（`provider` / `flush_min_turns` / `write_approval` / `memory_char_limit` / `user_char_limit`）
- 内置 provider 插件（2026-08 实测）：`supermemory`、`hindsight`、`honcho`、`mem0`、`byterover`、`retaindb`、`holographic`、`openviking`
- 暴露工具随 provider 注册（如 `supermemory_search/store/forget/profile`）
- API key 存 `~/.hermes/.env`；provider 专属配置可放 `~/.hermes/supermemory.json` 等
- 本地默认记忆 = `~/.hermes/memories/MEMORY.md` + `USER.md`（与 provider 并存，均每轮注入）

## 评估流程（先实测再下结论，禁止凭印象答）

1. **看配置**：`grep -A 10 -i "memory" ~/.hermes/config.yaml` 确认 provider 与参数
2. **用暴露工具实测**：对 provider 工具发不同查询，观察返回质量（相似度、内容完整性）
3. **直接调 SDK 看云端真实结构**（工具层可能掩盖问题）：Hermes venv 在 `~/.hermes/hermes-agent/venv/bin/python`，`import supermemory`（或 hindsight 等 SDK）查 documents.list / 原始响应字段——工具返回空 ≠ 云端无数据，先排查字段映射
4. **统计存储明细**：文档数、类型分布（full_session / explicit_memory）、正文完整度、最近写入时间
5. **对照本地 MEMORY 冗余度**：provider 注入内容与本地记忆重复时是双份上下文浪费

## 已知 Provider Quirks（实测 2026-08）

### supermemory（云端 api.supermemory.ai）
- **搜索空正文根因**：插件读 `item.memory` 字段；云端 `full_session` 类型条目只有 `summary` 无正文 → `search_mode=hybrid` 命中大量 `content` 为空的条目（只有相似度分数，对模型不可用）
- `search_mode=semantic/fulltext` 对中文查询返回 400（仅 hybrid 可用）
- `auto_capture` 每 `flush_min_turns` 轮把整个会话 POST `/v4/conversations` → 生成 full_session 摘要（无正文，检索价值低）
- SDK 坑：`add` 用 `content=` 关键字参数；`documents.list` 用 `container_tags=`；`delete` 用位置参数 id
- 评估结论（2026-08-16）：一周仅 6 条文档、搜索空正文严重 → 建议关 auto_capture + 修 summary fallback，或换 provider

### hindsight（vectorize-io/hindsight，20k★，MIT）
- Hermes **已内置 provider**（`plugins/memory/hindsight/`），默认云端 `api.hindsight.vectorize.io`，可配自托管 `base_url`
- 客户端：retain / recall / reflect；自托管 = Docker Compose / pip bare metal / embedded DB；embedding 默认走云端 API
- 支持平台：Linux x86_64+ARM64 / macOS arm64 / Windows（Intel Mac 用 slim 版）
- 切换成本低：`hermes memory setup` 填 key 即可，无需写集成代码

## 自托管硬件可行性清单（先查硬件再推荐）

记忆服务栈 = 引擎 + 数据库 + embedding 推理，推荐前必须核：

| 检查项 | 门槛 | 反例 |
|:-------|:-----|:-----|
| Docker 支持 | 群晖官方 Docker 套件**仅 x86** 型号（Plus/Value 系列） | play 系列（DS218play 等 ARM 机型）无 Docker，社区 hack 不稳 |
| 内存 | 建议 4GB+（1GB 连引擎+DB 都吃力，本地 embedding 至少 2GB+） | DS218play 仅 1GB 焊死 |
| CPU 架构 | x86_64 兼容性最好；ARM64 部分服务可跑 | RTD1296 (A53) 即使架构支持也带不动 |

**结论案例**：用户 DS218play（RTD1296 + 1GB + 无 Docker）无法自托管 hindsight/supermemory；可行替代 = Hindsight 云版 / Mac(Apple Silicon) 自托管 / x86 NAS。

## 切换 provider

- `hermes memory setup`（交互式，含 key 探测与连接验证）
- 换 provider 后**需新会话生效**，要告知用户
- 最简回退：删 `memory.provider` 或改回默认本地 memory

## Pitfalls

- **auto_capture 污染（2026-08-17 实测）**：诊断/运维会话中调用 retain 或触发 auto_capture（flush_min_turns=6），每条观察都会沉淀为记忆条目，形成「诊断→retain→更多噪音→再 retain」自强化循环。排查故障时应避免用记忆工具，或排查完逐条 PATCH 软删除（见下）
- **observation 类型不可直接 PATCH 软删除**（2026-08-17 实测）：`PATCH /memories/{id}` 对 observation（consolidation 派生的）返回 400；只有 world/experience 可软删除。正确路径：先 invalidate 父 experience → 级联删除派生 observation（会 404，属正常）
- 不要把「工具搜索返回空」当结论——先查字段映射（`item.memory` vs `summary`）
- Hermes venv 是 `~/.hermes/hermes-agent/venv/bin/python`，SDK 不一定在你默认 python
- 云 provider 与本地 MEMORY 高度重复时，注入上下文双份浪费，评估时量化重复度
- 环境差异（key 未配、包未装）不是 provider 本身的问题——先按 setup 流程修再评估

## 参考

- `references/supermemory-audit-2026-08.md` — supermemory 审计全流程：命令、响应结构、根因定位
- `references/hindsight-selfhosting.md` — Hindsight 概览 + Hermes 集成 + DS218play 硬件结论
