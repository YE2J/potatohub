# Hermes ↔ Coze 双向守护 — 详细记录

> 来源：2026-06-19 session，三 Agent 并行评审 + Coze 外部评审 + Phase 1 现场勘查

## 事故复盘

用户外出，Mac Mini 开机登录后离开。Hermes 要求重启并获 approve，但重启失败。只能通过 Coze 手动执行命令恢复。暴露：gateway 虽配了 `KeepAlive=true`，但 gateway **不在 launchd 中注册**（plist 存在但从未 loaded），所以 KeepAlive 不生效。

## Phase 1 现场勘查关键发现

| 发现 | 详情 | 影响 |
|------|------|------|
| coze-bridge 未安装 | 符号链接指向的 `dist/index.js` 不存在 | 脚本里所有 coze-bridge 命令无效 |
| gateway 不在 launchd | `ai.hermes.gateway` 未在 gui/501 注册 | `kickstart -k` 直接失败 |
| `open 扣子.app` cron 不可用 | 无 Aqua session → `kLSNoExecutableErr` | Hermes 无法从 cron 启动 Coze.app |
| 进程名是 "Coze" 非 "扣子" | CFBundleExecutable = "Coze" | `pgrep -f "扣子"` 永远不匹配 |
| Hermes 沙箱限制 | 终端工具无法 `ps`/`launchctl bootstrap` | launchd 注册需用户在 Terminal.app 手动执行 |

## v1 → v2 架构演进

### v1（废弃）
- 扣子每 30s 写心跳 + 每 60s 检查 Hermes
- Hermes 每 60s 检查 Coze（心跳 + coze-bridge + Coze.app）
- 互相重启

**致命问题**：扣子定时最小 10min，30s/60s 不可行。

### v2（当前）
```
治本层: launchd KeepAlive (实时进程守护，死掉自动拉)
诊断层: Hermes cron 每 60s 写心跳 + HTTP 自检
兜底层: Coze 每 10min curl /health + 心跳新鲜度检查
救火层: 主人说"救Hermes" → Coze 跑 rescue.sh (A||B)
```

**砍掉的内容**：扣子 30s/60s 心跳、Hermes 救 Coze.app、coze-bridge 依赖。

## 救命脚本设计原则

`~/.hermes/scripts/hermes_rescue.sh`：

1. **幂等**：先 `curl /health`，gateway 已健康则直接 exit 0
2. **方案 A 优先**：`launchctl kickstart -k`（治本）
3. **方案 B 兜底**：`nohup python -m hermes_cli.main gateway run`（直接启动）
4. **覆盖 3 个已知坑**：.env 丢失/损坏、Python AMFI 拦截、gateway 假死
5. **DRY_RUN 模式**：`DRY_RUN=1 bash rescue.sh` 仅模拟，不实际修改
6. **.env 内容校验**：不仅检查文件存在，还验证关键变量（WEIXIN_TOKEN 等）是否齐全

## Coze 侧需要做的事

| 定时 Agent | 频率 | 命令 |
|-----------|------|------|
| 深度健康检查 | 10min | curl + 心跳新鲜度，失败通知主人 |
| 主人口令触发 | 触发式 | 主人说"救Hermes" → `bash ~/.hermes/scripts/hermes_rescue.sh` |

## 评审记录

**Hermes 侧三 Agent 评审：**
- SRE：发现重启风暴无保护(H)、cron 单边静默失效(H)、Coze 活性检测盲区(H)
- 架构：心跳文件 IPC 可靠性(H)、扩展性受限(M)、不推荐引入第三方仲裁
- 实施：4 个阻塞问题（coze-bridge 未安装、launchd 无服务、open 不可用、pgrep 不匹配）

**Coze 外部评审：**
- 6 条建议全部采纳（砍 30s/60s、加 launchd、幂等、砍 Hermes 救 Coze、10min 检查、主人口令）
- 4 个非阻塞补丁（.env 内容校验、DRY_RUN、launchd StartInterval、Coze 告警）
- 建议实施顺序：先写 rescue.sh → 再注册 launchd → 再配 cron → 最后配 Coze

## 实现清单

| 文件 | 用途 | 状态 |
|------|------|------|
| `~/.hermes/scripts/hermes_rescue.sh` | 救命脚本（幂等 + 3坑 + A\|B） | ✅ |
| `~/.hermes/scripts/hermes_selfcheck.sh` | 心跳写入 + HTTP 自检 | ✅ |
| `~/.hermes/scripts/setup_launchd.sh` | 一键注册 launchd（需 Terminal.app） | ✅ |
| `~/.hermes/.env.backup` | .env 备份（防丢失） | ✅ |
| `~/Library/LaunchAgents/ai.hermes.gateway.plist` | KeepAlive + ThrottleInterval=120 | ✅ |
| `cron: hermes-selfcheck` | `* * * * *`, `no_agent=true` | ✅ |
| launchd bootstrap | 需用户在 Terminal.app 执行 `setup_launchd.sh` | ⚠️ |

## 已知待解决

- HTTP health check URL 需确认（`http://127.0.0.1:5432/health` 返回非 200）
- rescue.sh 在真实故障场景下未端到端验证
