---
name: git-worktree-isolation
description: Use when 多方案并行需隔离工作区。git worktree 方法论 + 非git环境目录隔离。
version: 1.0.0
author: hermes
license: MIT
metadata:
  hermes:
    tags: [git, worktree, 隔离, 并行开发]
    related_skills: [plan, review-driven-execution]
---

# Git Worktree 隔离工作区（改编自 obra/superpowers）

## When to Use

- 用户要求多方案并行实施、互不污染
- 开始实现计划前需要隔离当前分支/目录
- 实验性改动不想影响主环境（回测/选股/引擎调整）
- 判断标准：改动会影响现有代码 → 隔离；纯数据查询 → 不需要

## Overview

确保开发发生在隔离工作区。**核心原则：先检测现有隔离 → git worktree → 非git环境用目录隔离。绝不盲建。**

**适用场景（本机）：**
- `~/.hermes/potatohub` 等 **git 仓库** → 用 git worktree（本 skill 主流程）
- `~/my_quant_system`（**非git**）→ 用 Step 4 目录隔离替代方案（rsync 副本 + DB symlink）

## Step 0: 检测现有隔离

```bash
GIT_DIR=$(cd "$(git rev-parse --git-dir)" 2>/dev/null && pwd -P)
GIT_COMMON=$(cd "$(git rev-parse --git-common-dir)" 2>/dev/null && pwd -P)
BRANCH=$(git branch --show-current 2>/dev/null)
```

**Submodule guard：** `GIT_DIR != GIT_COMMON` 在 submodule 内也成立。先排除：
```bash
git rev-parse --show-superproject-working-tree 2>/dev/null  # 有输出=在submodule，当普通仓库处理
```

**判定：**
- `GIT_DIR != GIT_COMMON`（非submodule）→ 已在 worktree，跳过创建，直接报分支状态
- `GIT_DIR == GIT_COMMON` → 普通仓库，需要创建隔离
- **`git rev-parse` 报 "not a git repository"** → 非git环境，走 Step 4

创建 worktree 前**必须征得用户同意**（除非用户已明确要求）：
> "要建隔离 worktree 吗？可保护当前分支不受并行改动影响。"

## Step 1: 创建 git worktree

### 目录选择（优先级）
1. 用户明确指定的目录
2. 项目内已存在的 `.worktrees/`（隐藏，优先）或 `worktrees/`
3. 默认 `.worktrees/`（项目根）

### 安全验证（必须）
```bash
git check-ignore -q .worktrees 2>/dev/null || git check-ignore -q worktrees 2>/dev/null
```
**未忽略则先加 .gitignore 并提交**，否则 worktree 内容会被误提交进仓库。

### 创建
```bash
git worktree add "$LOCATION/$BRANCH_NAME" -b "$BRANCH_NAME"
cd "$LOCATION/$BRANCH_NAME"
```
失败（sandbox 权限拒绝）→ 告知用户，就地开发。

## Step 2: 项目 Setup

```bash
# Python
if [ -f requirements.txt ]; then pip install -r requirements.txt; fi
if [ -f pyproject.toml ]; then pip install -e .; fi
# Node / Rust / Go 同理按项目实际
```

## Step 3: 验证干净基线

跑项目测试套件（pytest / npm test 等）。**测试失败 → 停下报告，让用户决定是否继续**（脏基线会让后续所有失败无法归因）。

成功报告：
```
Worktree ready at <full-path>
Tests passing (<N> tests, 0 failures)
Ready to implement <feature-name>
```

## Step 4: 非git环境替代方案（my_quant_system 等）

无 git 时用**目录副本隔离**。关键：不复制大文件，用 symlink 指向原库。

```bash
# 1. 建隔离副本（排除大文件与缓存）
rsync -a --delete \
  --exclude='stock_data.db' --exclude='stock_data.db-wal' --exclude='stock_data.db-shm' \
  --exclude='data/' --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' \
  ~/my_quant_system/ ~/my_quant_system_work_<feature>/

# 2. DB symlink（避免复制6.9GB；注意：并发写同一DB有锁冲突，只读场景安全）
ln -s ~/my_quant_system/stock_data.db ~/my_quant_system_work_<feature>/stock_data.db
```

**DB symlink 注意：**
- 只读实验（回测/分析/选股）→ 安全
- 需要写 DB → 复制一份独立 DB 或用临时库，避免与主库 WAL 锁冲突

### 验证
```bash
cd ~/my_quant_system_work_<feature>
python -c "import sys; sys.path.insert(0,'.'); import config; print(config.DB_PATH)"
# 再跑引擎的 --help 或一次最小运行确认环境可用
```

### 清理
```bash
rm -rf ~/my_quant_system_work_<feature>   # symlink 一并删除，原库不受影响
```

## Quick Reference

| 情形 | 动作 |
|-------|------|
| 已在 git worktree | 跳过创建（Step 0） |
| 在 submodule | 当普通仓库（Step 0 guard） |
| git 仓库 | git worktree（Step 1-3） |
| 非 git 仓库（my_quant_system） | 目录隔离 rsync+symlink（Step 4） |
| `.worktrees/` 已存在 | 用它（验证忽略） |
| 目录未 ignore | 加 .gitignore + 提交 |
| 测试失败基线 | 停下报告，不盲进 |
| 只读实验 | DB symlink 安全 |
| 要写 DB | 复制独立 DB，勿 symlink |

## Common Rationalizations

| 借口 | 现实 |
|-------|------|
| "我明显不在 worktree，不用查" | 跑 Step 0。harness 隔离和 submodule 都会骗过肉眼 |
| "worktree 目录肯定已 ignore" | 跑 `git check-ignore`。未忽略会整个提交进仓库 |
| "新工作区很干净，基线测试能省" | 脏基线让后续失败无法归因。现在跑，失败由用户决定 |
| "直接复制整个目录多简单" | 6.9GB DB 复制几分钟；symlink 秒级且不占盘 |
| "并发写 DB 没问题吧" | WAL 锁冲突会静默损坏数据。写场景必须独立副本 |

## 来源

改编自 obra/superpowers `skills/using-git-worktrees/SKILL.md`（MIT，27.4万★），2026-08-19 提取。Step 4 为针对本机非git量化系统的本地化补充。
