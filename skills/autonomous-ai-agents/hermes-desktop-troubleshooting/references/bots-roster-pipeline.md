# BOTS roster 数据链路（hermes-bots 插件）与 2026-08-23 回归实例

## 数据流
BotsPane（`plugin.js:11519`）→ `useRoster()`（`plugin.js:3891`）→ queryFn：
1. `activeBotRoute()` → 活跃 bot route（**本 bug 点：该函数全库无定义**）
2. `requestForBot(activeBot, 'profiles.list', {})` → `host.requestProfile` / `host.request`
3. `host.agents()`（可选，union roster；Electron main IPC `hermes:agents:roster` → `enumerateRegistryAgentSources` → `GET /api/profiles`）
4. `mergeMultiSourceRoster(local, union, activeConnectionId, $lastRoster)`

BotsPane 容错（`plugin.js:11567-11568`）：
```js
const live = Array.isArray(data?.profiles) ? data.profiles : null
const source = live ?? (error ? $lastRoster.get() : [])
```
→ queryFn 抛错时回退空缓存 → 空列表；且 `roster.length===0` 时不显示 staleNotice → 全白无提示。

## 迁移
- 键：`BOT_META_V1_KEY='bot-meta'`，`BOT_META_V2_KEY='bot-meta-v2'`，`BOT_META_MIGRATION_KEY='bot-meta-v2-migrated'`（plugin.js 89-91）
- `migrateBotMeta()`：v2Committed && v2 → 直接用 v2；否则 v1→v2 需 sole-local 拓扑证明（`host.agents()` + `profileRoutes`），失败回退 v1
- 存储位于 plugin storage（Electron Local Storage/leveldb），压缩格式 `strings` 看不到键名

## 2026-08-23 回归实例（症状→证据→根因→修复）
- **症状**：更新后 BOTS 标签页空白。截图：BOTS 激活、中间全白、底部 `+ New Agent` 按钮。
- **后端探针**：`/api/profiles` 返回 7 profiles（default/orchestrator/worker-*）；WS `profiles.list` 返回 7 → **后端完好，数据未丢**。
- **前端证据**：`dist/assets/index-D60Bdhjk.js` 中 `activeBotRoute` 仅 2 处调用、0 定义；源码 plugin.js、SDK `host` 对象（src/sdk/index.ts）、preload 均无 → `useRoster` queryFn 抛 `ReferenceError`。
- **引入点**：`git log -S "activeBotRoute"` → 503d863fcd（仓库大规模重写，10052 文件）加入调用未带定义；8-18 版 e02d1e41fc 无此引用。
- **修复（待执行，未验证）**：plugin.js 补 `activeBotRoute()`（从 `host.state.connectionId`/`host.state.profile` 推导 `{connectionId, profile, targetProfile, mode}`）→ `npm run build` → 重启应用；或等上游修复。
- **同类排查提醒**：后端版本号（/api/status version）与桌面 package.json version 不同步本身即线索；`desktop-build-stamp.json` builtAt 用于对齐"何时更新"。
