---
name: hermes-mcp-servers
title: "Hermes MCP 服务器管理：添加、验证、排障"
description: "Use when 添加/配置/验证 Hermes 的 MCP 服务器。"
tags: [hermes, mcp, integration, config]
---

# Hermes MCP 服务器管理

给 Hermes 接入第三方 MCP 服务器（数据源、图书、GitHub 等）的完整流程。Hermes 内置原生 MCP 客户端：启动时连接服务器、自动发现工具、以 `mcp_<server>_<tool>` 前缀注入对话。

## 核心约束

| 事项 | 规则 |
|:-----|:-----|
| 修改配置 | **禁止 patch/write_file 改 config.yaml**（`Refusing to write to Hermes config file`）→ 必须用 `hermes mcp add` CLI |
| 生效时机 | 无热加载，新会话（`/reset`）才注入工具 |
| 凭据 | stdio 服务器子进程**不继承 shell 环境**，凭据必须写在 `--env`（CLI）或 config.yaml 的 `env:` 段 |
| 工具命名 | `mcp_zlibrary_search_books` 形式（连字符/点转下划线） |

## 添加流程

```bash
# ① stdio 服务器（本地命令，最常见）
hermes mcp add zlibrary --command zlibrary-mcp \
  --env ZLIBRARY_EMAIL=xxx ZLIBRARY_PASSWORD=yyy ZLIBRARY_MIRROR=https://z-lib.li \
  --connect-timeout 60

# ② HTTP 服务器（远程 URL，如 tushareMcp）
hermes mcp add myserver --url https://api.example.com/mcp
```

### 🚨 交互式确认陷阱

`hermes mcp add` 发现工具后停在 `Enable all N tools? [Y/n/select]:`。**非交互终端（terminal 工具）下会显示 `Cancelled` 且不保存**。解决：管道喂 Y：

```bash
echo "Y" | hermes mcp add zlibrary --command zlibrary-mcp --env ...
# ✓ Saved 'zlibrary' to ~/.hermes/config.yaml (13/13 tools enabled)
```

### 🚨 UV-based npm MCP 包需要 uv sync

npm 包分两类：
- **纯 Node**：`npm install -g pkg` 后直接可用
- **UV-based**（如 zlibrary-mcp v1.4.0）：npm 只装 TypeScript/Node 侧，Python bridge 需要包目录内 `.venv`。首次调用报 `UV has not initialized the environment. Please run: uv sync`。

修复（在包安装目录内执行）：
```bash
cd /Users/yellow/.npm-global/lib/node_modules/<pkg>/ && uv sync
```

安装后先用 `zlibrary-mcp`（无参数跑一次）检查是否有 Missing env 警告，确认服务端本身能启动。

## 验证（不重启会话直连测工具）

`hermes mcp list` 只证明服务器注册成功，**不代表凭据可用**。要用真实工具调用验证凭据：系统 python3 常缺 `mcp` 包 → 用 Hermes venv python 跑 `mcp` ClientSession + stdio_client 直连服务器调工具（如 `search_books`）。完整脚本见 `references/standalone-verify.md`。

```bash
~/.hermes/hermes-agent/venv/bin/python /tmp/mcp_verify.py
# TOOLS: 13
# SEARCH_RESULT: {...真实书籍数据...}   ← 凭据验证通过
```

## 常用命令

```bash
hermes mcp list                 # 已注册服务器 + 工具数 + 状态
hermes mcp test zlibrary        # 测试连接
hermes mcp configure zlibrary   # 勾选启用哪些工具
hermes mcp add --help           # 看参数（--url / --command / --env / --connect-timeout）
```

## 陷阱汇总

1. 非交互终端下 `hermes mcp add` 交互确认会静默取消 → `echo "Y" |`
2. UV-based npm 包缺 `.venv` → 包目录内 `uv sync`
3. 系统 python3 无 `mcp` 模块 → 用 `~/.hermes/hermes-agent/venv/bin/python`
4. stdio 子进程不继承凭据环境 → 必须 `--env` 显式传
5. 注册 ≠ 凭据有效 → 必须真实工具调用验证

## 参考

- `references/standalone-verify.md` — 不重启会话的 MCP 工具直连验证脚本（ClientSession + stdio_client）
- `references/zlibrary-mcp.md` — zlibrary-mcp 服务器细节（环境变量、13 工具清单、镜像说明）
