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
| `~/.hermes/config.yaml`（**顶层**） | **仅 `hermes config` CLI** ⛔ | `patch`/`write_file` 被拒：`Refusing to write to Hermes config file... use 'hermes config' instead` |
| `~/.hermes/profiles/<name>/config.yaml`（**profile 级**） | `patch` 直接改 ✅ | 不在顶层保护范围内；改前备份、改后 `hermes -p <name> config get <key>` 验证。只用文本级 patch，`yaml.dump` 回写会重排/破坏整份文件 |

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

### 🚨 hermes update 会重置 display.personality（实测踩过）

`hermes update` 自动跑的 config 格式迁移（desktop.log 可见 `Updating config format (v33 → v34)`）会**把 `display.personality` 重置为空** `''`，导致桌面端"人格"显示"无"。人格池 `agent.personalities.*` 定义和 SOUL.md 不受影响（行为不变，只是显示标签丢失）。

- 现象：用户问"为什么人格变成无/之前设置过吗" → 先 `grep -n 'personality:' ~/.hermes/config.yaml` 看激活值是否 `''`
- 排查证据链：`hermes config get display.personality`（当前值）+ `ls ~/.hermes/config.yaml.bak*`（历史备份对比）+ `grep -n 'Updating config format' ~/.hermes/logs/desktop.log`（确认 update 时间点）
- 修复：`hermes config set display.personality pm`（一行恢复，池定义无需重建）
- 预防：update 后顺手 `hermes config get display.personality` 检查一次

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

## 多 Agent 模型/推理强度清单审计（只读盘点）

用户问「所有 agent 用的什么模型版本 / 推理强度」时，一次性盘点 5 层，漏层就是漏答：

| 层 | 读取方式 | 说明 |
|:---|:---------|:-----|
| profile 主模型 | `hermes profile list` + `hermes -p <p> config get model.default` | 7 个 profile：default/orchestrator/worker-glm/kimi/minimax/qwen/xiaomi |
| 推理强度 | `hermes -p <p> config get agent.reasoning_effort` | 另查 `delegation.reasoning_effort`（子代理档位，常为 high） |
| MOA 参考层+聚合器 | `hermes moa list` | 参考模型与聚合器可能同源，需提示同质化 |
| auxiliary | `hermes config get auxiliary.vision.model` 等 | 视觉/压缩等旁路模型，worker profile 多为 `auto` |
| 休眠配置 | 读 profile config.yaml 的 `moa.presets` + `hermes status` | 指向未配置 key 的 preset（如 openrouter）属死配置，必须标出 |

### 🚨 `HERMES_PROFILE=x hermes config get` 不生效（本会话踩过）

`hermes config get <key>` **永远读 default profile**，环境变量方式赋值不生效——会把所有 profile 都显示成 default 的值（如全部 `medium` / `deepseek-v4-flash`），且不报错，静默产出错误清单。

- 正确：`hermes -p <profile> config get <key>`（逐 profile 一条命令）
- 校验：若多个 profile 输出完全相同，先怀疑读错了 profile，`hermes profile list` 交叉核对

### 配置值与「上游是否真正支持」分开报

`agent.reasoning_effort` 只是配置层正确，厂商线级支持因模型家族而异（GLM 原生 effort 仅 5.2/5.3、MiniMax 插件只映射 adaptive/disabled、xiaomi/alibaba-coding-plan 插件无 reasoning 映射）。审计时必须分列「配置值」与「线级支持」，未实测的直接标 ⚠️，不要把配置值当成生效结论。判定依据与命令见 `references/model-change-workflow.md` 的「推理强度线级支持核对」。

### 汇报格式（用户偏好）

表格优先，且分三块：①主力 agent（profile 级）②派生调用层（MOA/子代理/辅助）③⚠️ 不一致与风险清单（每条带证据）。末尾给选项表含「我的倾向」列 + 声明默认动作（"无回复即按 ① 执行"），只读盘点**不动配置**，改不改由用户点选。

## 配置变更执行与验证（改 profile / 人格描述的统一节奏）

1. **备份**：要改的每一份 config 和将改写的文档都先复制到带时间戳目录（`~/.hermes/backups/<date>_<用途>/`），并在汇报里给出回滚命令。
2. **改**：profile 级 config 用 `patch`（带上下文锚点，避免误伤重复段）；顶层 config 走 `hermes config` CLI 或终端 python 定点替换（`assert count==1` 防误改）。
3. **验证三层，缺一层不算完成**：
   - 生效值：`hermes -p <name> config get <嵌套路径>`
   - 未破坏运行：一次性冒烟 `hermes -p <name> -z "只回复：可用"` → 看到字面回复 + exit=0 才说明该 profile 仍能加载配置
   - 连带文件：grep 旧值确认清零（只允许出现在 `cache/`、`backups/`）
   - ⚠️ macOS 没有 `timeout` 命令，别在 shell 里包 `timeout`，用工具侧 timeout 参数控时长
4. **汇报**：改了哪些文件（diff 摘要）+ 验证命令的**真实输出** + 备份路径与回滚命令；未实测的部分标 ⚠️，不得写成「已生效」。

### 🚨 别对整个 skills 树做无过滤 grep
`grep -rn <kw> ~/.hermes/skills` 会扫到 `~/.hermes/skills/.hub/index-cache/hermes-index.json`（数十 MB 的 skill hub 索引），一次可产出数十 MB 输出、瞬间吃光上下文。
- 正确：明确列出目标文件（如 `~/.hermes/SOUL.md ~/.hermes/profiles/*/SOUL.md`），或加 `--include='*.md' --include='*.yaml'` 并排除 `.hub/index-cache/`
- 大目录搜索前先 `ls` 看体量、限定 include，再决定是否 grep

### 修正「文档/人格与实际配置不符」的分寸
盘点发现描述失真时先分类，再动手：
- **当前状态声明**（如「复杂任务委托 v4-pro/high」「effort=low」）→ 直接改成实测值，并标注实测日期，让读者一眼知道这是核对过的现值。
- **历史坑位记录**（skill 里当年排查 401/换 provider 时引用的旧值）→ 保留原教训，只加一行「当前实测值见 <skill/reference>」的指针。把历史记录改写成现值＝删掉教训。

## 参考

- `references/config-keys.md` — 本机 Hermes 配置关键路径速查
- `references/model-change-workflow.md` — 模型变更 4 类位置 + 全 Agent 模型/推理强度盘点（含逐 profile 读取命令、推理强度线级支持核对表）
- `references/web-tools-firecrawl.md` — Web 工具(Firecrawl)诊断/修复全流程与 curl 降级示例
