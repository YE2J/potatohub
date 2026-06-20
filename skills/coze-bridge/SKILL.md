---
name: coze-bridge
description: "本地 Agent 连接到 Coze 平台：配对绑定、daemon 管理、解绑重来、常见问题排查。"
version: 1.0.0
author: agent
platforms: [macos, linux]
metadata:
  hermes:
    tags: [Coze, Agent, Bridge, Daemon, 扣子]
prerequisites:
  commands: [coze-bridge, npm]
---

# coze-bridge: 连接本地 Agent 到 Coze 平台

coze-bridge 是一个本地 daemon，将本机 Agent（如 Hermes）桥接到 Coze 云端，使用户可以在 Coze 平台上与本地 Agent 对话。

## 触发条件

- 用户要绑定/连接 Coze 与本地 Agent
- 用户在 Coze 上看不到本地 Agent
- 需要重新配对、解绑、排查连接问题

## 完整流程

### 1. 配对绑定

```bash
# 用户从 Coze 平台获取 pat-token 和 pair-code 后立即执行
npx -y --registry=https://registry.npmmirror.com coze-bridge@latest \
  --pat-token=<sat_xxx> \
  --pair-code=<xxx>
```

> **注意**：配对码有时效性，用户生成后必须尽快执行，否则会报 "pair code not found or expired"。

配对成功后提示"已配对连接完成"，用户需在 Coze 平台点击"我已执行"。

### 2. 全局安装

`npx` 一次性运行后，daemon 进程会随 npx 退出而终止（SIGTERM）。必须全局安装以保证 daemon 持久运行：

```bash
npm install -g --registry=https://registry.npmmirror.com coze-bridge@latest
```

### 3. 开机自启

```bash
coze-bridge service install
```

### 4. 验证状态

```bash
coze-bridge status
```

关注字段：
- `running: true` — daemon 在线
- `agents: []` — 空列表表示云端还未触发 Agent 创建（正常，等用户在 Coze 上对话后会自动创建）

### 5. 查看日志

```bash
coze-bridge log -n 50
```

## 常用命令

| 命令 | 用途 |
|------|------|
| `coze-bridge status` | 查看 daemon 状态 |
| `coze-bridge log -n 100` | 查看最近 100 行日志 |
| `coze-bridge log --agent-id <id>` | 查看指定 agent 日志 |
| `coze-bridge connect` | 用已存储的 PAT 重连（无需 pair-code） |
| `coze-bridge stop` | 停止 daemon |
| `coze-bridge reload` | 回收所有 agent 子进程 |
| `coze-bridge update` | 升级到最新版 |
| `coze-bridge purge` | 完全清除：停止 daemon + 卸载 supervisor + 删除 `~/.coze/bridge`，**保留** `~/.coze/agents` 工作区 |

## 完全解绑重来

```bash
coze-bridge purge
# 然后从 Coze 平台重新获取配对码，回到步骤 1
```

## 常见问题

### 配对码过期
```
pair code not found or expired
```

配对码有时效性。去 Coze 平台重新生成，拿到后立刻执行配对命令。

### 本地 Agent 在 Coze 上看不到
1. `coze-bridge status` 确认 `running: true`
2. 确认用户在 Coze 平台点击了"我已执行"
3. `coze-bridge log -n 30` 检查是否有错误
4. 云端触发 Agent 后，`~/.coze/agents/` 目录会被创建，agents 列表出现条目

### npx 执行后 daemon 消失
`npx` 运行完进程即退出，daemon 随之终止。必须 `npm install -g` 全局安装后再 `coze-bridge service install` 确保持久化。

### 符号链接断裂（模块文件丢失）
症状：`coze-bridge` 命令报 `Cannot find module`，符号链接指向的 `dist/index.js` 不存在。

原因：npm 全局安装的模块文件被删除或 `node_modules` 被清理。

修复：
```bash
npm install -g --registry=https://registry.npmmirror.com coze-bridge@latest
```

验证：
```bash
ls -la $(readlink -f $(which coze-bridge))
# 预期：dist/index.js 存在
coze-bridge --help
```
