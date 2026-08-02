# WeChat iLink 推送限流排障

## 根因分析

### DNS 瞬断触发连锁反应

```
gateway 轮询 → DNS 解析失败 (nodename nor servname provided, or not known)
  → 连接 iLink 失败 × 5 次重试
    → iLink 服务端限制该账号推送 (sendmessage rate limited)
      → 后续所有推送均被拒 (即使 DNS 已恢复)
```

**关键诊断线索**：限流日志之前必有 `Cannot connect to host ilinkai.weixin.qq.com:443`。

DNS 在终端 (`nslookup`/`dig`) 解析正常 ≠ gateway 进程的 DNS 正常。Gateway 作为 launchd 服务可能使用不同的 DNS 上下文或缓存了失败状态。

### 限流持久化 — 重试循环陷阱

每次重试都会消耗新的限流配额，导致冷却时间被不断重置：

```
07:00:18  → DNS 失败 → 5 次重试 → 限流 (30s)
07:33:41  → cron 触发 → 限流 (延长)
07:36:08  → 再触发 → 仍限流
```

**修复前提**：停止所有推送尝试，让限流自然冷却 ≥15-30 分钟。

## 诊断步骤

### 1. 确认限流规模

```bash
# 统计限流次数
grep -c "send failed.*rate limited" ~/.hermes/logs/gateway.error.log

# 检查限流之前是否有 DNS 故障（根因）
grep "Cannot connect to host ilinkai" ~/.hermes/logs/gateway.error.log | tail -5

# 检查 cron 推送目标
cronjob action=list | grep -A2 delivery_error
```

### 2. 验证 DNS 连通性

```bash
# 终端 DNS（不一定代表 gateway 上下文）
nslookup ilinkai.weixin.qq.com 2>&1 | grep Address

# ping 测试连通性
ping -c 2 ilinkai.weixin.qq.com 2>&1
```

### 3. Gateway 恢复流程

当限流持续且 gateway 无法自动恢复：

```bash
# 从 gateway 内部只能直接 kill PID（launchd 自动重启）
GW_PID=$(pgrep -f "hermes.*gateway" | head -1)
kill -9 "$GW_PID"
# 注意：hermes gateway restart / launchctl kickstart 均被拦截
```

Restart 后：
- 等 ≥60 秒让 iLink WebSocket 重连 + 限流冷却
- 先用小测试消息验证恢复
- 如果仍限流，停止触发 ≥15 分钟

## cron 模式选择

| 模式 | 推送失败处理 | 限流时表现 |
|------|------------|-----------|
| `no_agent: true` (脚本) | **不重试** — 错失消息 | 脚本执行正常，但输出丢了 |
| `no_agent: false` (LLM) | **自恢复** — 检测到失败可重试 | 限流解除后自动补推 |

推微信的 cron 尽量用 LLM 模式。

## no_agent 脚本无 stdout 的静默模式

`no_agent=true` + 脚本无 stdout = 不触发任何推送（即使 `deliver: origin`）。

## 修复方案

| 方案 | 操作 | 适合场景 |
|------|------|---------|
| **A** 改为 local | `deliver: local` | 无需实时通知的 cron |
| **B** 聚合推送 | 多个 local cron → 一个汇总 cron | 每日晨报类 |
| **C** 散列调度 | 错开整点半点 | 多个 cron 同时完成 |
| **D** 换平台 | 推到 Telegram/SMS | 关键告警 |

## 关键认知

- 限流 **不影响** 双向对话（用户发消息→Hermes回复）
- 每次失败后 gateway 会重试，但重试也在 cooldown 内会再失败
- 限流是 iLink 平台侧控制，Hermes 侧无法绕过
