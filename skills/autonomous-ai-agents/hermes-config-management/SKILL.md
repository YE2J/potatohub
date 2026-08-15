---
name: hermes-config-management
title: "Hermes 配置与人格管理（SOUL.md / config.yaml / personalities）"
description: "Use when 用户要求改人格/性格/角色或修改 Hermes 自身配置。"
tags: [hermes, config, persona, personality, soul]
---

# Hermes 配置与人格管理

用户常要求「改人格」「查看你的角色设置」「切换性格」——这些操作落在两个文件：`~/.hermes/SOUL.md`（persona 灵魂文件）和 `~/.hermes/config.yaml`（配置，含 personality 池）。两者修改方式**完全不同**。

## 文件访问权限速查

| 文件 | 可写方式 | 说明 |
|:-----|:---------|:-----|
| `~/.hermes/SOUL.md` | `write_file` 直接覆盖 ✅ | persona 文件，**不受保护**；但头部可能有历史 UTF-16 编码乱码残留，`read_file` 可能报 Binary |
| `~/.hermes/config.yaml` | **仅 `hermes config` CLI** ⛔ | `patch`/`write_file` 会被拒绝：`Refusing to write to Hermes config file... use 'hermes config' instead` |

## SOUL.md（persona 文件）

- 定义 agent 的人格、语气、强制工作流程。内容直接进系统提示。
- 读取注意：若 `read_file` 报 Binary（历史乱码），用 `iconv -f UTF-16 -t UTF-8` 或 `cat` 兜底；重写 `write_file` 会顺带清掉乱码。
- **改前必备份**：`cp ~/.hermes/SOUL.md ~/.hermes/SOUL.md.bak.$(date +%Y%m%d_%H%M%S)`
- 生效时机：**下一个新会话**，当前会话仍沿用旧上下文（要告知用户）。
- **profile 专属 SOUL.md**：每个 profile（orchestrator/worker-*）有自己的 `~/.hermes/profiles/<name>/SOUL.md`，修改方式相同（备份+write_file 覆盖+告知生效时机）。orchestrator SOUL 是 Kanban 调度官人格（见 kanban-worker-fleet skill）。
- **PM 四步人格模式（2026-08 用户确认）**：用户要求人格/工作流时，默认采用 PM 模式——①需求确认（用户非科班，需求模糊→提问指导完善；不合理→列理由由用户确认；明确后发完整确认）②方案设计（盘点现状+MOA讨论+用户确认前不写代码）③任务实现 ④测试验证（MOA测试后再汇报）。全任务统一执行、禁止跳步；简单任务豁免已取消（资源节约≠流程豁免）。已固化进主 SOUL.md 与 orchestrator SOUL。

## config.yaml personality 管理（核心陷阱）

结构：人格池在 `agent.personalities.<name>`（如 `agent.personalities.technical`），**激活开关**在 `display.personality`（取值 = 池里某个 name）。

```bash
# 1. 激活人格（正确，顶层键直接生效）
hermes config set display.personality pm

# 2. 把人格定义加进池子 —— 必须用完整嵌套路径！
hermes config set 'agent.personalities.pm' "You are a seasoned project manager..."
```

### 🚨 嵌套键陷阱（本会话踩过）

`hermes config set 'personalities.pm' ...`（漏了 `agent.` 前缀）会**静默创建顶层 `personalities:` 键**，而不是写入 `agent.personalities`。命令显示 `✓ Set` 但 YAML 里出现了两个 personalities 段，`display.personality: pm` 读不到池里的定义。

- 正确路径：`agent.personalities.<name>`
- 若已写错：`hermes config unset 'personalities.pm'` 清理顶层键
- `hermes config set` 对未识别键会警告 `not a recognized config key — saved anyway`，看到此警告立即查路径

### 验证流程

```bash
hermes config get display.personality      # 确认激活值
hermes config get 'agent.personalities.pm' # 确认池里有定义
python3 -c "import yaml; yaml.safe_load(open('/Users/yellow/.hermes/config.yaml')); print('OK')"  # 语法校验
grep -n '^agent:\|^personalities:\|^  personalities:' ~/.hermes/config.yaml  # 确认只有一个 personalities 段且归属正确
```

## 记忆（memory）容量管理

记忆是两个文件：`~/.hermes/memories/MEMORY.md`（agent 笔记，默认 2,200 字符 ≈ 800 tokens）与 `~/.hermes/memories/USER.md`（用户画像，默认 1,375 字符 ≈ 500 tokens），每会话开始以**冻结快照**注入系统提示。

### 容量配置（config.yaml memory 段）

```yaml
memory:
  memory_char_limit: 2200   # MEMORY.md 上限
  user_char_limit: 1375     # USER.md 上限
```

- **无硬性最大上限**：官方（issue #16831 维护者确认）**未实现**值域校验，可设任意正整数。
- **真实天花板 = 模型上下文窗口**：memory 每轮注入 system prompt，设多大就每轮吃多少 token。128K 窗口下 memory 建议 ≤10~15K tokens（约 30K~45K 字符），过大挤占对话空间、触发更频繁压缩。
- 修改：`hermes config set memory.memory_char_limit 4000`（已验证，改完 `grep -A8 '^memory:' ~/.hermes/config.yaml` 确认）。

### 🚨 会话启动限制陷阱（本会话踩过）

`memory_char_limit` 是**会话启动时读取**的。改完 config 后，**当前会话的 memory 工具仍按旧上限校验**（报 `memory would be at X/2200 chars -- over the limit`），新会话才生效。

- 若要**当前立即写入超旧上限的内容**（如恢复被压缩条目）：直接 `write_file` 覆盖 `~/.hermes/memories/MEMORY.md`（格式：条目用 `§` 单独成行分隔，可含多行）；memory 工具底层就是写这个文件。
- 写入后本会话仍显示旧快照（提示头 `2,172/2,200 chars`），**新会话 `/new` 或重启后**才显示新上限与新内容——主动告知用户。
- 验证：`python3 -c "content=open('/Users/yellow/.hermes/memories/MEMORY.md',encoding='utf-8').read(); print(len(content), len([e for e in content.split('§') if e.strip()]))"`（字符数 + 条目数）。

### 容量满时被压缩条目的恢复工作流

memory 满时 agent 会 `replace` 合并 / `remove` 删除条目腾空间，无 `.bak` 备份。恢复方法：

1. `session_search(query="记忆 合并 OR 压缩 OR 删除 OR memory remove replace", role_filter="user,assistant,tool", sort="newest")` 找历史 memory 工具调用记录——**旧条目的原文**常完整保留在 tool-call arguments 里（`old_text` 即被替换前的文本）。
2. 被删条目的痕迹线索：当前条目若以 `⑤⑥` 开头说明前面 ①~④ 已被删；合并后的条目内容明显残缺时用**真实数据源重建**（如 cron 列表用 `cronjob action=list` 拉 28 个真实任务，不凭记忆编造）。
3. `write_file` 覆盖 MEMORY.md，控制总字符 ≤ 新上限，验证后告知新会话生效。

## Web 工具（Firecrawl）配置与故障排查

web_search/web_extract 依赖 Firecrawl 后端。报错「Web tools are not configured. Set FIRECRAWL_API_KEY...」= 三条路都没配：云 key（`FIRECRAWL_API_KEY`）、自托管（`FIRECRAWL_API_URL`）、Nous Portal 登录（托管）。

### 诊断（一条命令确认）
```bash
hermes status | grep -iE 'Firecrawl|Nous Portal'
# Firecrawl ✗ (not set) + Nous Portal ✗ not logged in → 确认未配置
```

### 修复三选一
| 方案 | 操作 | 说明 |
|:-----|:-----|:-----|
| ① Nous Portal 登录 | `hermes portal login`（交互式设备码流程） | 免费额度托管 Firecrawl；`hermes portal` 无子命令 = login |
| ② 云 Firecrawl | `.env` 加 `FIRECRAWL_API_KEY=...` | 付费 firecrawl.dev |
| ③ 自托管 | `.env` 加 `FIRECRAWL_API_URL=...` | 需自己部署 Firecrawl 实例 |

### 🚨 `hermes portal login` 设备码流程陷阱（本会话踩过）
- 交互式命令会**无限轮询等用户授权**：必须 `pty=true + background=true` 跑；前台跑会 timeout（exit 124）
- 输出授权 URL（`...manage-subscription?user_code=XXXX-XXXX`）+ 验证码；**用户可用手机等任意设备**打开 URL 输码完成授权——设备码流程不绑定本机
- 验证码几分钟内过期：用户改期时 kill 等待进程，下次重新发起生成新 code
- login 是 one-shot onboarding，可能「pick a model, set Nous as provider」——登录后核对 `hermes config get model.provider`（本机原为 deepseek）；只加凭据不想动模型用 `hermes auth add nous --type oauth`
- 配置完成前需要联网的任务用 curl 降级（GitHub API、公开接口），示例见 `references/web-tools-firecrawl.md`

## 参考

- `references/config-keys.md` — 本机 Hermes 配置关键路径速查
- `references/web-tools-firecrawl.md` — Web 工具(Firecrawl)诊断/修复全流程与 curl 降级示例
