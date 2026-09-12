# 双 Agent 自动同步：sync/ 文件信号通道（2026-09-10 与 Coze 金融专家敲定并端到端实测）

适用：双 Agent（本地 Hermes + Coze 端 agent）需「不每次手动喊同步」的自动协作，且 Coze 侧无常驻进程无法实时盯文件。@ 即时通道为主，文件通道留档 + 兜底。

## 分工现实（决定设计）

| 侧 | 触发能力 | 限制 |
|---|---|---|
| 本地 Hermes | 被群 @ 唤起；coze-bridge daemon 常驻；hermes cron */10 可扫文件 | cron 是 no-agent 脚本任务，**不能注入 agent 会话**——扫到 REQ 只留痕，真正处理仍靠对方 @ 唤起 |
| Coze 端 agent | 被群 @ 唤起；Calendar 定时（每日静默时段扫漏网） | 无常驻进程，不能实时监听文件 |

结论：**文件通道是留档+兜底，@ 才是主通道**。写完 REQ/RSP 必须群里 @ 对方一次（双保险）。

## 目录与命名

- 共享项目目录下建 `sync/`（如 `/Users/yellow/Coze/Drive/<项目>/sync/`，双端同一挂载）。
- `REQ_<YYYYMMDD_NN>_<topic>.md`（请求）；`RSP_<YYYYMMDD_NN>_<topic>.md`（回执）；seq 同日递增，topic 短横线小写英文。

## 头部字段（必填）

```
[seq]: YYYYMMDD_NN
[from]: <agent 名>
[to]: <agent 名>
[created_at]: YYYY-MM-DD HH:MM (UTC+8)
[status]: open | done
```
消费方处理完把 status 置 done（**不移动文件，保留留痕**），可附 `[consumed_at]` / `[consumed_by]`。按 seq 幂等：done 永不重复处理。

## 触发 / 超时 / 静默

- 即时：请求方写完文件后群里 @ 对方（@ 即唤起）。
- 兜底：本地 cron */10 扫 `[to:小马]+status=open`（留痕不弹窗）；Coze 侧 Calendar 每日静默时段扫 `[to:金融專家]+open` 漏网。
- 30 分钟 open 未处理：cron/Calendar 判定后群里 @ 对方；仅「需用户裁决 / 超时告警」才 @ 用户。
- 静默纪律：轮询不弹窗不通知；Coze 侧 00:00-06:00 静默区间。

## 死循环防护

- response 类回执消费后**不回 @、不再产 RSP**（回执的回执禁止）。
- @ 只用于「请求方需要对方执行动作」；文件按 seq 幂等。

## 落地命令要点

```bash
mkdir -p <项目>/sync
# 监控脚本 ~/.hermes/scripts/scan_sync_open.py：无 open → print("CLEAN")（稳定输出）
hermes cron create "*/10 * * * *" --name "sync-双Agent信号轮询" \
  --script scan_sync_open.py --no-agent --deliver local
```

⚠️ **hermes cron 能力边界**（实测）：`--monitor-script` 与 `--no-agent` 互斥（monitor 的意义是唤醒 AGENT，不能 no-agent）；no-agent 脚本任务 stdout 空=静默、非空=投递到 deliver。no-agent 不能唤起 agent 处理文件——所以轮询只做留痕，处理靠 @。

## 端到端验收（selftest）

1. 发 ping（`--mode request` @ 对方，正文「同步机制 ping 测试…收到请回复」）确认双向 @ 链路。
2. 写 `REQ_<today>_001_sync_selftest.md`（[to:对方]）→ 群 @。
3. 对方消费 REQ 置 done、写 RSP 置 open、群 @ 回；自己消费 RSP 置 done。
4. 全部 status=done 即打通；cron 下一轮自然扫到 RSP 顺带验证轮询留痕。

## 判定经验

- 不要凭「文件在云端能写」假设对方可读——selftest 里让对方明确回「链路OK」并双向置 done 才算打通。
- 消息交叉：对方回复 ping 确认时可能尚未处理到你的完整回执（两个 message_id 并行），此时**不再重复发同一内容**，指出已发回执的 message_id 即可；对 response 类消息不回 at_agent（防循环）。
