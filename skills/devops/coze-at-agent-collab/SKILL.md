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
| 400 `response does not match a collaboration request` | reply-to-message-id 用错（误用 message_id），或该请求已失效；⚠️ 也发生在**目标 agent 已被删除**（turn aborted: agent_deleted -32020）——请求随原 agent 一起死亡，id 再对也回不上 | 先 `coze agent member list` 确认自己还在、发起方还在；若本地侧是新实例接管，别再重试 response，走下方「接管/补交场景」改发 request |
| E1103 `MISSING_OPTION` | **request 模式也强制要 `--reply-to-message-id`**（权威文档没标 request 的必填性） | 用当前 turn coze-context 的 `reply_to_message_id`（普通群聊消息时 = message_id）补上 |
| E1000 `Invalid --targets: expected a JSON array` | targets 内含未转义换行/引号，被 shell 破坏 | 见下「JSON 构造铁律」：Python json.dumps 落盘再读入 |
| `1000500 RPC调用错误` | `--reply-to-message-id` 用了**对方 response 消息的 id**——那条消息是回执、不是发给我的 request，不构成可回复的协作请求 | 改用**当前 turn** coze-context 的 `message_id`/`reply_to_message_id` 重发（同参数一次即通） |
| 500 `at_agent service is unavailable` | 扣子平台侧服务故障，与本地无关 | 停止手动高频重试，走降级流程 |
| 认证错误 | token 问题 | `coze auth status --format json` |

## 服务端故障降级流程（2026-08-26 实测：500 持续 >1 小时未恢复）

1. 结果落盘两处：agent workspace/（持久备查）+ Coze 共享 Drive 目录（如 `/Users/yellow/Coze/Drive/<项目>/`，用户可直接打开）。
2. `terminal(background=true)` 起后台重试循环，间隔 ≥8 分钟，输出命中 `"code": *0` 即 break；配 notify_on_complete。
3. 群聊内直接贴出完整结果文本兜底，保证主人当下可用。
4. 主人问进度时把两件事分开表述：「任务本身已完成」vs「回执通道平台故障」，附最新 logid 与下次重试计划，避免被误认为没干活。

## 接管/补交场景（2026-09-02 实测：原 agent 崩溃+删除，新实例接管）

旧 agent 处理协作请求中途崩溃（如 billing 429）后被删除 → 入站请求的 response 通道随之失效。**即使 reply-to-message-id 完全正确，`--mode response` 也报 400**，因为请求已随原 agent 死亡。恢复路径：

1. 不要反复重试 response（不会成功）。
2. `coze agent member list` 确认当前存活成员：删除后群里可能只剩发起方 + 新本地实例，claw_id 全变。
3. 内容照常落盘 Coze Drive 共享目录（如 `/Users/yellow/Coze/Drive/<项目>/`）。
4. 改发 **`--mode request` 给原发起方**，message 开头注明「前序协作请求发起时原本地 agent 已崩溃删除，现由接管实例 <名字> 补交」，正文 = 原要求的完整报告；回复人汇总给用户。
5. 向用户汇报时说明：任务内容本身已完成并送达（附 message_id/status=accepted），与旧 agent 崩溃是两件事。

## 发起协作请求（--mode request）

要点（详见注入的权威文档）：先 `coze agent member list --project-id <group_id> --format json` 选 `user_type=2` 且有 `claw_id` 的成员；`--targets` 为 JSON 数组（≤3 个，每项含 target_claw_id/message/response_target_type）；排除自己；不转发密钥。

⚠️ request 模式**同样必须** `--reply-to-message-id <当前 turn 的 reply_to_message_id>`（权威文档模板中有但陷阱清单常被忽略；缺它报 E1103）。

### JSON 构造铁律（--targets 含长中文/换行时）

内联 `--targets '[...$MSG...]'` 遇换行/引号必被 shell 破坏（E1000）。用 Python 构造合法 JSON 落盘再读入：

```bash
python3 -c "
import json
msg = open('report.md', encoding='utf-8').read()
msg = '【补交说明】...\n\n' + msg[:3700]   # 单条 ≤4000 码点
open('targets.json','w',encoding='utf-8').write(json.dumps(
    [{'target_claw_id':'<对方claw_id>','message':msg,'response_target_type':'agent'}],
    ensure_ascii=False))
"
coze agent at --mode request \
  --project-id "<group_id>" --source-claw-id "<agent_id>" \
  --reply-to-message-id "<reply_to_message_id>" \
  --targets "$(cat targets.json)" --format json
```

成功判据同 response：`code=0` + `data.status="accepted"` + `data.message_id` 非空。

## 双 Agent 自动同步（文件信号通道）

当协作需要「不每次手动喊同步」且对方无常驻进程时，用共享目录 `sync/` 文件通道 + @ 双保险（REQ/RSP 命名、头部字段、seq 幂等、超时告警、死循环防护、端到端 selftest 验收全部见 `references/sync-file-channel.md`）。核心：**文件通道只是留档+兜底，@ 才是主通道**；hermes cron 的 `--monitor-script` 与 `--no-agent` 互斥，no-agent 轮询不能唤起 agent 处理文件。

### 🔴 用户要求：任务完成 → 主动 @ 对方，不要每次问「要不要同步」

用户明确纠正过：完成任何评审/分析/交付物后，应**自动**把结论 @ 发起方（写 `sync/RSP_*` + 即时 at_agent request），不必先问「要我同步吗」。提问式同步在用户眼里等于没做自动化。

落点：把「产出结论 → 落 RSP → @ 对方」作为任务收尾的固定一步，仅在「需要用户裁决」「跨项目影响」「对外发送」三类事项上才停下来确认。

### 能力边界（勿承诺自动化做不到的事）

| 环节 | 能否自动 | 说明 |
|------|:--------:|------|
| 对方写 REQ → 我侧发现 | ✅ | cron `*/10` no-agent 扫 `[to:我] + status=open`，命中输出非空留痕 |
| 我发现后**实际处理** | ⚠️ | no-agent 脚本只能检测，**唤起处理仍靠对方 @ 我**（cron 不能注入会话） |
| 我产出 RSP → **自动 @ 对方** | ❌ | 需 agent 在会话中跑 `coze agent at`；cron 无法代发 @。**不要把这条写成已实现** |

→ 向用户/对方描述同步机制时必须区分「已实现」（文件留痕 + @ 主通道）与「未实现」（cron 自动代发 @），否则会被当成链路故障反复追问。

## 陷阱清单

- 全部 ID 保持十进制字符串，严禁过 float/int64 精度丢失。
- 无请求级幂等保证：超时后不要自动盲重试，先保留 logid 核实；确认失败才可重发（可能产生重复协作消息）。
- 尺寸限制：reply_to_message_id ≤256 UTF-8 字节；单条 response ≤4,000 字符、全部 targets 合计 ≤32KiB。
- 收到 mode=response 时只消费合成，绝不再调 at_agent（防死循环）。
- agent_deleted（turn aborted code -32020）后：旧 agent 的协作请求全部作废，接管实例一律走「接管/补交场景」的 request 补交，勿试 response。
- 每次以当前 turn 的 coze-context 取 ID（account_id/group_id/agent_id/reply_to_message_id），不跨 turn 复用——agent 被删重建后 agent_id 会变（2026-09-02：7676100391154729225 → 7680925600332431616）。
