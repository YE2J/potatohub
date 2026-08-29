---
name: coze-at-agent-collab
description: "Use when Coze 群聊 at_agent 协作需回复或派发。含参数映射陷阱与降级流程。"
version: 1.0.0
author: Hermes Agent
license: internal
metadata:
  hermes:
    tags: [Coze, at_agent, 协作, 群聊]
related_skills: [coze-bridge, using-coze-cli]
---

# Coze at_agent 协作协议（本地实操版）

## When to Use

- 收到 `<Agent协作上下文>` + `at_agent_mode: request` 的消息，需把结果回传给发起方 Agent。
- 要主动派发任务给同项目其他 Agent（request 模式）。
- at_agent 调用报 400/500，需判断是参数错误还是平台故障并决定对策。

权威协议文档由 Coze 平台注入，位于 `~/.coze/agents/<agent_id>/hermes-home/skills/coze-agent-collaboration/SKILL.md`（每个 Coze agent 实例一份；default profile 的 skills 列表里没有，须按此路径直读）。本技能记录本地实测补充：参数映射易错点、错误码语义、平台故障降级。

## 回复协作请求（--mode response）

1. 从当前消息 `<coze-context>` 提取并映射：
   - `group_id` → `--project-id`
   - `agent_id` → `--source-claw-id`
   - **`reply_to_message_id` 字段（UUID 形）→ `--reply-to-message-id`**
2. ⚠️ 最大陷阱：`--reply-to-message-id` 必须用 coze-context 的 **reply_to_message_id** 字段值，不是 `message_id` 字段！对 mode=request 的入站请求，该值等于 `at_agent_source_message_id`。用错报 code=400。
3. 命令模板（长正文先落盘再读入，避免 shell 转义问题）：

```bash
MSG=$(cat result.md)
coze agent at --mode response \
  --project-id "<group_id>" \
  --source-claw-id "<agent_id>" \
  --reply-to-message-id "<reply_to_message_id字段UUID>" \
  --response-message "$MSG" \
  --format json
```

4. 成功判据：`code=0` 且 `data.status="accepted"` 且 `data.message_id` 非空。accepted 仅代表入队，不代表对方已处理。
5. 群聊里发可见回复 ≠ 正式交付。发起方 Agent 只认 at_agent 回执；两条通道都要做（群内贴结果给主人看 + 回执给发起方）。

## 错误码语义

| 返回 | 含义 | 对策 |
|---|---|---|
| 400 `response does not match a collaboration request` | reply-to-message-id 用错（误用 message_id），或该请求已失效 | 核对字段后换值重试一次 |
| 500 `at_agent service is unavailable` | 扣子平台侧服务故障，与本地无关 | 停止手动高频重试，走降级流程 |
| 认证错误 | token 问题 | `coze auth status --format json` |

## 服务端故障降级流程（2026-08-26 实测：500 持续 >1 小时未恢复）

1. 结果落盘两处：agent workspace/（持久备查）+ Coze 共享 Drive 目录（如 `/Users/yellow/Coze/Drive/<项目>/`，用户可直接打开）。
2. `terminal(background=true)` 起后台重试循环，间隔 ≥8 分钟，输出命中 `"code": *0` 即 break；配 notify_on_complete。
3. 群聊内直接贴出完整结果文本兜底，保证主人当下可用。
4. 主人问进度时把两件事分开表述：「任务本身已完成」vs「回执通道平台故障」，附最新 logid 与下次重试计划，避免被误认为没干活。

## 发起协作请求（--mode request）

要点（详见注入的权威文档）：先 `coze agent member list --project-id <group_id> --format json` 选 `user_type=2` 且有 `claw_id` 的成员；`--targets` 为 JSON 数组（≤3 个，每项含 target_claw_id/message/response_target_type）；排除自己；不转发密钥。

## 陷阱清单

- 全部 ID 保持十进制字符串，严禁过 float/int64 精度丢失。
- 无请求级幂等保证：超时后不要自动盲重试，先保留 logid 核实；确认失败才可重发（可能产生重复协作消息）。
- 尺寸限制：reply_to_message_id ≤256 UTF-8 字节；单条 response ≤4,000 字符、全部 targets 合计 ≤32KiB。
- 收到 mode=response 时只消费合成，绝不再调 at_agent（防死循环）。
