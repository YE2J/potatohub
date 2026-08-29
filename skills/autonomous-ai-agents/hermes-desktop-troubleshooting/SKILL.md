---
name: hermes-desktop-troubleshooting
description: "Use when 桌面端栏目空白/更新后异常，诊断 Hermes 桌面应用故障。"
version: 1.0.0
---

# Hermes Desktop Troubleshooting

诊断 Hermes 桌面应用（Electron）运行时故障的流程：先验证后端数据源，再查前端渲染层。覆盖"更新后某栏目空白"这类回归。

## 架构（谁拥有什么）
- **Electron 主进程**（`apps/desktop/electron/`）：机器、进程生命周期、后端 serve 管理、IPC（`host.*`，含 `agents` roster）
- **渲染进程**（`apps/desktop/src/` + `src/plugins/`）：导航、UI、roster 等体验层；只是后端真值的缓存（merge 不 clobber）
- **后端 serve**（`hermes_cli.main serve`）：会话、工具、模型；REST + WS JSON-RPC
- 三方各自为权威。排查时后端数据正常 ≠ 前端正常，前端报错 ≠ 数据丢失。

## 关键路径
| 内容 | 路径 |
|---|---|
| 桌面用户数据 | `~/Library/Application Support/Hermes/`（connection.json v1、connections.json v2、backend-ownership.json、Local Storage/leveldb） |
| 桌面源码 | `~/.hermes/hermes-agent/apps/desktop/` |
| 打包产物 | `apps/desktop/release/mac-arm64/Hermes.app/Contents/Resources/app.asar`（+ `.unpacked/dist`） |
| 构建时间戳 | `~/.hermes/desktop-build-stamp.json`（builtAt，UTC） |
| 日志 | `~/.hermes/logs/desktop.log`（含 `[renderer console]`）、`gui.log`（后端）、`gateway.log`、`errors.log` |
| 后端 serve 注册 | `backend-ownership.json`（pid/profile/端口）+ `connections.json` |

## 调试阶梯（按序执行，先证明数据源再查前端）
1. **确认更新时间与版本**：`desktop-build-stamp.json` builtAt；`app.asar` mtime；`package.json` version；后端 `/api/status` version —— 判断前后端是否同一次更新
2. **后端存活**：`backend-ownership.json` → `ps aux | grep "hermes_cli.main serve"`；`lsof -iTCP -sTCP:LISTEN -P | grep python`
3. **取 serve token 探 REST**：
   `ps eww -p <serve_pid> | tr ' ' '\n' | grep HERMES_DASHBOARD_SESSION_TOKEN`
   `curl -H "Authorization: Bearer $TOKEN" http://127.0.0.1:<port>/api/profiles`（及 `/api/status`）
4. **探 WS JSON-RPC**（profiles.list 等）：`websockets` 连 `ws://127.0.0.1:<port>/api/ws?token=$TOKEN`，发 `{"jsonrpc":"2.0","id":1,"method":"profiles.list","params":{}}`，等 `id==1` 的 result（首条收到的可能是 `gateway.ready` 事件，需循环收）
5. **查渲染层错误**：`grep "renderer console" desktop.log` —— Uncaught Error 行会指向具体 bundle 文件
6. **查 bundle 引用缺陷**：grep 未定义符号（`dist/assets/index-*.js`），确认"只有调用、零定义"
7. **查插件数据流/迁移**（如 hermes-bots：`BotsPane` → `useRoster` → `requestForBot` → `host.request` → `profiles.list`）

## 常见故障类
- **更新回归（2026-08-23 实锤）**：打包进 bundle 的插件调用未定义函数（如 `activeBotRoute`）→ `ReferenceError` → useQuery 失败 → 列表空。特征：后端探针全正常、bundle grep 只有调用无定义、`git log -S <符号>` 可定位引入 commit。修复：补定义重建 dist，或等上游。
- **前后端版本 skew**：desktop dist 与 serve 版本不同步（`desktop_contract` 不匹配）。
- **连接模式**：v1 `connection.json` mode=remote 时本地枚举被 defer（`resolveRegistryLocalRoute`/`shouldDeferLocalEnumeration`）→ BOTS 空。查 `~/Library/Application Support/Hermes/connection.json`。
- **插件 meta 迁移**：hermes-bots V1→V2（键 `bot-meta` / `bot-meta-v2` / `bot-meta-v2-migrated`），迁移失败会回退 v1。

## BOTS 群聊数据隔离（2026-08-25 源码定位）

**"群聊"是桌面端 UI 层的功能，不是后端 agent 功能。** 群聊消息活在前端，后端 Python 进程和 cron/wiki 均无访问路径：

| 环节 | 实查 | 源码位置 |
|---|---|---|
| 群聊房间状态 | 渲染进程内存 atom（`$groupChats = atom({})`），非数据库 | `hermes-bots/plugin.js:438` |
| 房间持久化 | Electron 插件 storage（`pluginCtx.storage.set('group-chats', ...)` → `~/Library/Application Support/Hermes/Local Storage/leveldb/`，键 `P-bots.group-chats`） | `plugin.js:1061-1068` |
| 移动端镜像 | 经 default profile `ui_meta` 同步，纯展示投影（display-only），不落 agent 会话库 | `plugin.js:626` |
| bot 间消息 | `hermes -p <bot> chat --in ~ -c "Bot Chat"`——各 bot 回复只写自己 profile 的 Bot Chat，不广播 | `plugin.js:16` |

**排查结论**：worker profile 目录（glm/kimi/xiaomi/qwen/auditor）**全空**——无 state.db、无 config、无会话文件，它们只是被调用的模型不留痕；default state.db 里只有 4 个 "Bot Chat" 标题的显示投影会话。群聊原始数据**从未进入任何后端可读存储**（8-24 实测 hermes 收不到其他 bot 回复是同一根因）。

**影响**：任何期望"自动抓取 BOTS 群聊内容"的下游（wiki cron、脚本、日报）都不可行。唯一桥接路径：主 Agent 汇总确认后的结论 → 写入 wiki `queries/_inbox/` → cron 每日消费归档。

## 陷阱
- Local Storage/leveldb 是压缩的，`strings` 看不到键名，别浪费时间
- serve 端点无 token 返回 401；token 从 `ps eww` 读（同用户可读），不用猜
- `gui.log` 是后端日志；渲染层错误只在 `desktop.log`
- 压缩 bundle 中未定义符号保留原名（如 `activeBotRoute`），可直接 grep 计数（`grep -c`）
- 空列表时 UI 容错把 error 回退到空缓存：`live ?? (error ? $lastRoster.get() : [])`，且 `roster.length===0` 时不显示"刷新失败"提示 → **界面全白无提示 ≠ 数据丢失**，先探后端再下结论

## 参考
- `references/bots-roster-pipeline.md` — BOTS roster 完整数据链路、迁移逻辑与 2026-08-23 回归实例证据
