---
name: coze-code
version: 0.3.2
description: "Coze Coding 项目开发工作流：创建项目、发送需求消息、查询状态、预览、部署、环境变量管理、域名管理、技能管理、数据库管理。当用户需要创建/管理 Coze 项目、发送开发需求、部署应用、管理数据库、或使用 coze code * 任意命令时触发。"
metadata:
  requires:
    bins: ["coze"]
  cliHelp: "coze code --help"
---

# Coze Coding 工作流

> **前置条件：** 先阅读 [`../SKILL.md`](../SKILL.md) 完成认证和上下文配置。
> **执行前必做：** 执行任何 `code` 命令前，必须先阅读对应命令的 reference 文档，再调用命令。

## 核心概念

- **Project（项目）**：Coze Coding 的核心实体，包含 AI 编程对话历史和代码仓库。通过 `project create` 创建。
- **Message（消息）**：发送给项目的需求或指令，由 AI 异步处理。通过 `message send` 发送。
- **Deploy（部署）**：将项目部署到生产环境。通过 `deploy` 执行。
- **Preview（预览）**：获取沙盒预览链接。通过 `preview` 获取。
- **Env（环境变量）**：项目级 Secrets 管理，支持 dev/prod 环境。
- **Domain（域名）**：项目自定义域名绑定。
- **Skill（技能）**：项目关联的外部技能，可挂载/解绑到默认会话，也可上传/删除个人技能。
- **Model（模型）**：项目默认会话使用的模型。通过 `model list/set` 查看与设置（会话维度）。
- **Tools（工具）**：项目默认会话启用的工具（如联网搜索、图片生成）。通过 `tools list/enable/disable` 管理（会话维度）。
- **Database（数据库）**：空间级 Supabase 数据库，支持 SQL 执行、类型生成、Schema 导出和 PITR 回滚。
- **Git（Git 集成）**：Git 平台 OAuth 授权管理和仓库搜索。通过 `git auth` 管理授权，`git search` 搜索仓库。
- **Repo（远程仓库）**：项目的远程仓库绑定和同步管理。通过 `repo` 命令组进行创建、绑定、推送、拉取等操作。

## Agent 快速执行顺序

1. **判断任务类型**
   - 新建项目 → `project create`
   - 迭代开发 → `message send` → [`message status`](references/coze-code-message.md) → [`preview`](references/coze-code-preview.md) → [`deploy`](references/coze-code-deploy.md)
   - 查询/管理 → `project list/get/delete`
   - 配置管理 → `env` / `domain` / `skill` / `model` / `tools`
   - 数据库管理 → `db create / list / get / query / gen-types / dump / rollback / status / delete`
2. **确认前置条件**
   - 已登录? (`coze auth status`)
   - 已选组织和空间?
   - 如果是已有项目: 拿到 projectId
3. **执行命令前必读对应 reference**

## 标准 Coze Coding 工作流

### Step 0: 使用 `@` 语法引用本地文件

在 `coze code message send` 中，可直接用 `@文件路径` 引用本地文件，CLI 会自动上传并作为附件发送。

- 只支持引用**文件**（不支持目录）。
- 文件路径可以是相对路径或绝对路径。

```bash
coze code message send "请使用这张图片作为头像 @./avatar.png" -p <project-id>
coze code message send "对比 @src/old.ts 和 @src/new.ts 的差异" -p <project-id>
```

详细用法参见 [`coze-code-message.md`](references/coze-code-message.md)。

### Step 1: 创建项目

详细参数和示例参见 [`coze-code-project.md`](references/coze-code-project.md)。

```bash
coze code project create --message "创建一个聊天机器人" --type web --format json
```

- `--message` 和 `--type` 均为**必填参数**（`--message` 无 `-m` 短别名）。
- **`--type` 接受**：`agent | workflow | app | skill | web | miniprogram | assistant`（源码 `resolveProjectType` 还兼容 `webapp`）。其中 `web` / `app` 是最常用类型；`assistant` 走模板复制创建。传入未知类型会报 `E1005`。
- 其它可选项：`--chat-mode <ask|agent|dangerous_confirm|plan>`、`--model-name`、`--tool-name`（可多次传）、`--design`（`--chat-mode plan` 时自动开启）。
- `--wait` 选项会等待项目创建完成（包括首次 AI 消息响应）后再返回。
- 记录返回的 `projectId`。

#### Step 1.1: 准确识别项目类型（按"产品形态"判定，勿被功能词带偏）

创建前**必须**先根据用户意图确定 `--type`，**不要默认用 `web`**。

> **核心原则：决定 `--type` 的是用户描述的「产品形态 / 载体」（小程序 / App / 网页 / 智能体 / 工作流 …），而不是「功能品类」（抽奖 / 商城 / 聊天 / 投票 / 点餐 …）。功能词只说明"做什么"，不改变类型。**

判定步骤：
1. 先在用户文本里找**形态词**：命中即按形态词定 `--type`，**忽略功能词的干扰**。
2. 文本中**没有任何形态词、只有功能描述**（如"做个抽奖工具""做个商城"）时，才反问用户想要哪种形态，**不要擅自默认 `web`**。

| 形态词（出现即命中，可带任意功能前缀） | 推荐 `--type` |
|------------------|--------------|
| "小程序"、"微信小程序"（如 抽奖小程序 / 商城小程序 / 投票小程序 / 点餐小程序 / 预约小程序） | `miniprogram` |
| "App / 应用 / 移动端应用 / 手机 App / 原生应用"（如 记账 App / 健身应用） | `app` |
| "网页 / 网站 / Web 页面 / 落地页 / 官网 / H5"（如 企业官网 / 活动落地页） | `web` |
| "智能体 / Agent / 机器人 / 客服 bot" | `agent` |
| "工作流 / 自动化流程" | `workflow` |
| "技能 / skill 插件" | `skill` |
| "助手 / assistant" | `assistant` |

判定要点：
- **「小程序」是强信号**：只要文本里出现"小程序"三字，一律 `--type miniprogram`，**绝不**因为前面带"抽奖 / 商城 / 聊天"等功能词而归成 `web`。
- **「App / 应用」**（而非"网页 / 网站 / 页面"）一律 `--type app`；仅当用户明确说"Web 应用 / 网页应用"时才用 `web`。
- **多个形态词冲突**（如"做个网页版小程序"）或**完全没有形态词**时，**先反问**用户要哪种形态，确认后再创建，不要擅自默认。

典型纠错：
- "做一个抽奖小程序" → `--type miniprogram`（✗ 不是 `web`；"抽奖"是功能，"小程序"才是形态）
- "做个记账应用" → `--type app`（✗ 不是 `web`）
- "做个商城" → 先反问（小程序 / App / 网页？），✗ 不要默认 `web`

#### Step 1.2: 仅创建项目，默认不自动部署

- `project create` **只负责创建项目并触发首次 AI 开发**，**绝不**自动部署。创建成功后**不要**主动执行 `deploy`。
- 部署是独立动作，**必须**由用户明确要求"部署 / 上线"，且 `message status` 为 `done` 时才执行（见 Step 3 / Step 4）。

#### Step 1.3: 创建成功后的标准回复（含「打开项目」入口）

项目创建成功后（无论是否 `--wait`），回复用户时**必须**附上「打开项目」入口，链接指向项目对话页面，方便用户直接跳转，省去在项目列表 / 历史会话中二次查找。

**链接来源**：`project create` 的 `--format json` 返回值中已含 `project_url` 字段（CLI 按**项目类型**自动生成域名：`web` / `app` / `miniprogram` 为 `https://www.coze.cn/p/<project_id>`，其它类型为 `https://code.coze.cn/p/<project_id>`）。**直接读取 `project_url` 透传给用户，不要自行拼接链接。**

回复模板（创建成功、AI 仍在后台开发时，`<project_url>` 取自返回值）：

```
✅ 项目已创建成功，正在为你开发中…
- 🔗 打开项目：<project_url>
- 可继续发送需求迭代，或稍候查看开发结果。
```

#### Step 1.4: 开发任务完成后的引导文案

**创建后必须主动跟进到开发完成**，不能停在"正在开发中"就结束。查询状态**优先使用主动轮询**的方式：
- **首选**：创建后**主动轮询** `coze code message status -p <project_id> --format json`（`message status` 无 `--wait`，需自行间隔轮询），直到状态为 `done`，**不要**让用户自己去查状态。
- 备选：创建时加 `--wait` 让 CLI 等到首次 AI 开发完成再返回（仅在确有需要时使用，状态跟进仍以主动轮询为准）。

待状态为 `done` 后，向用户给出后续操作引导（**不要**自动执行部署）：

**「预览效果」一行仅 `web` 类型项目才显示**。当 `--type web` 时，**先主动获取预览地址再给引导**：执行 `coze code preview <project_id> --format json`，读取返回的 `preview_url`，把预览地址**直接展示**给用户，而不是只丢一条 `coze code preview` 命令让用户自己跑。

- 沙盒初始化通常需 **1-3 分钟**，若 `preview_url` 暂未就绪可稍后重试一次。
- **非 `web` 类型**（`app` / `miniprogram` / `agent` / `workflow` / `skill` / `assistant`）一律**省略「预览效果」整行**，不展示预览地址。

引导文案（`<project_url>` / `<preview_url>` 取自返回值）：

```
✅ 开发任务已完成，未自动部署，你可以继续选择：
- 🛠 继续对话修改页面/文案/功能
- 🔗 打开项目：<project_url>
- 👀 预览效果：<preview_url>        # 仅 web 类型显示此行
- 🚀 确认后发起部署
```

#### Step 1.5: 创建失败场景的文案提示

当 `project create` 失败（如报错、未返回 `project_id`、上下文缺失等）时，**不要**只把原始错误堆栈丢给用户，按以下模板友好提示并引导用户补充信息后重试：

```
项目创建失败
你可以重新发起创建，或补充更明确的项目类型、页面需求和目标空间后再试。
```

### Step 2: 发送需求

详细参数和示例参见 [`coze-code-message.md`](references/coze-code-message.md)。

```bash
coze code message send "请优化应用配色..." \
  --project-id <project-id> \
  --format json
```

- `-p` / `--project-id` 指定项目 ID，也可通过 `COZE_PROJECT_ID` 环境变量设置（仅 `message` 命令组支持该环境变量回退）。
- 支持 stdin 管道输入，但**必须显式加 `--stdin`**：`cat requirements.txt | coze code message send "请按此需求开发" --stdin -p <id>`。
- `--format json` 时输出 NDJSON 事件流，每行一个 JSON 对象。**必须按行解析**。

### Step 3: 部署前先查状态

详细说明参见 [`coze-code-message.md`](references/coze-code-message.md)。

- 收到"部署"要求时，**必须**先确认 `message status` 已结束。
- 状态为 `processing` 时禁止直接部署，否则可能出现 `refs/heads/main does not exist` 等错误。

```bash
coze code message status --project-id <project-id> --format json
```

- `message status` 是**单次查询**（无 `--wait`，不轮询）：状态为 `done` 时自动拉取并返回 answer，否则返回当前状态。需要等待时，请自行轮询调用。
- `message cancel` 可取消正在进行的消息。

### Step 4: 部署

详细参数和坑点参见 [`coze-code-deploy.md`](references/coze-code-deploy.md)。

- `deploy` 直接接收项目 ID 作为**位置参数**，**不要**加 `--project-id`。

```bash
coze code deploy <project-id> --format json
```

- `--wait` 会轮询等待部署完成（轮询间隔 3 秒）。
- 部署前项目必须有 commit 记录，否则会失败。

### Step 5: 查询部署结果 & 获取预览

```bash
# 查询部署状态
coze code deploy status <project-id> --format json

# 获取预览链接
coze code preview <project-id>
```

- 默认查询最新部署记录，也可通过 `--deploy-id <id>` 指定具体部署记录。
- 直到 `status` 为 `Succeeded`，再把线上地址返回给用户。
- 沙盒初始化通常需要 1-3 分钟。

## Agent 禁止行为

- 不要在 `project create` 后**自动部署**——创建只完成项目创建与首次 AI 开发，部署须等用户明确要求
- 不要在 `project create` 后**停在"正在开发中"就结束**——查询状态优先主动轮询 `message status` 到 `done`（`--wait` 仅备选），再给出完成引导文案（Step 1.4），不要让用户自己查状态
- 不要在项目创建成功后**漏掉「打开项目」入口**——回复必须附上返回值里的 `project_url`（不要自行拼接链接）
- 不要被功能词带偏项目类型——`--type` 由**产品形态词**（小程序 / App / 网页 …）决定，不由功能品类词（抽奖 / 商城 / 聊天 …）决定；尤其"X 小程序"一律 `--type miniprogram`、"App / 应用"一律 `--type app`，**绝不**默认 `web`，无形态词时先反问（见 Step 1.1）
- 不要在 message 仍为 **processing** 时直接部署
- 不要对 deploy 使用 **`--project-id`**（它是位置参数！）
- 不要给 project create 的 **`--type`** 传受支持列表（`agent|workflow|app|skill|web|miniprogram|assistant`）以外的值，否则报 `E1005`
- 不要在没有 `--stdin` 时指望管道输入被读取（`message send` 必须显式加 `--stdin` 才读 stdin）
- 不要忽略 **NDJSON 事件流的逐行解析要求**
- 不要把本地路径发给用户（必须走 file upload 返回在线链接）

## 长耗时任务处理

| 命令 | 轮询间隔 | 说明 |
|------|----------|------|
| `coze code project create --wait` | — | 等待项目创建和首次 AI 响应完成 |
| `coze code deploy --wait` | 3 秒 | 等待部署到达终态 |
| `coze code deploy status --wait` | 3 秒 | 复用父级 `deploy --wait`，等待部署到达终态 |
| `coze code deploy fix --wait` | — | 等待修复消息响应 |

> `message status` **没有** `--wait`，需要等待时请自行轮询；`deploy status` 自身不声明 `--wait`，而是读取父命令 `deploy --wait`。

优先使用 `--wait` 让 CLI 自动轮询。到达终态后，必须主动把最终结果反馈给用户。

## 意图 → 命令索引

| 意图 | 推荐命令 | 备注 |
|------|---------|------|
| 创建新项目 | `coze code project create` | `--type` 支持 agent/workflow/app/skill/web/miniprogram/assistant（常用 web/app） |
| 列出/查看项目 | `coze code project list/get` | 支持按类型/名称筛选 |
| 删除项目 | `coze code project delete` | 不可逆操作 |
| 导入项目 | `coze code project import -s <github\|local>` | 导入后自动发后台初始化 query（可用 `message status` 跟进），返回值含 `project_url` |
| 发送开发需求 | `coze code message send` | 支持 @文件引用；stdin 需加 `--stdin` |
| 查询任务状态 | `coze code message status` | 单次查询，无 --wait |
| 取消任务 | `coze code message cancel` | |
| 查看对话历史 | `coze code message history` | 支持 --before / --after 翻页 |
| 部署到生产 | `coze code deploy <id>` | **位置参数**, 不用 --project-id；支持 --commit-id/--table-name/--connector-id |
| 查询部署状态 | `coze code deploy status <id>` | |
| 列出部署历史 | `coze code deploy list <id>` | 支持 --page-size/--page-token |
| 修复失败部署 | `coze code deploy fix <id>` | 把部署日志发给 AI 修复，仅 Failed 可修 |
| 获取预览链接 | `coze code preview <id>` | 沙盒初始化需 1-3 分钟；仅 Web/App 类型可预览 |
| 管理环境变量 | `coze code env set/list/delete` | list 支持 --env dev\|prod；delete 固定 dev；set 不支持 Skill 项目 |
| 管理自定义域名 | `coze code domain add/list/remove` | add 仅接受单级域名(如 example.com) |
| 挂载/解绑技能 | `coze code skill add/remove` | 对默认会话挂载或解绑 |
| 列出技能 | `coze code skill list` | 支持 --my 列个人技能 |
| 上传个人技能 | `coze code skill upload <file> -p <id>` | 上传 .skill 文件，冲突自动覆盖；`-p` 必填 |
| 删除个人技能 | `coze code skill delete <skill-id> -p <id>` | 永久删除技能本体(区别于 remove)；`-p` 必填 |
| 查看/设置模型 | `coze code model list/set` | 会话维度，set 需校验模型可用 |
| 启用/禁用工具 | `coze code tools list/enable/disable` | 会话维度 |
| 创建数据库 | `coze code db create` | 自动生成名称和凭据 |
| 列出数据库 | `coze code db list` | 支持 --all 自动翻页 |
| 查看数据库详情 | `coze code db get --db-id <id>` | 含连接 URL 和凭据 |
| 执行 SQL | `coze code db query --db-id <id> --sql "..."` | 危险 SQL 需 --confirm |
| 生成 TS 类型 | `coze code db gen-types --db-id <id>` | 基于 PostgREST OpenAPI |
| 导出 Schema | `coze code db dump --db-id <id>` | 支持 --schema-only / --data-only |
| 回滚数据库 | `coze code db rollback --db-id <id> --timestamp <ts> --confirm` | PITR 回滚，需 --confirm |
| 查看数据库状态 | `coze code db status --db-id <id>` | 含回滚进度 |
| 删除数据库 | `coze code db delete --db-id <id> --confirm` | 不可逆，需 --confirm |
| 授权 Git 平台 | `coze code git auth login` | 需要浏览器完成 OAuth |
| 检查 Git 授权状态 | `coze code git auth status` | |
| 取消 Git 授权 | `coze code git auth logout` | 影响空间下所有项目 |
| 搜索远程仓库 | `coze code git search` | 需先完成 Git 授权 |
| 创建远程仓库 | `coze code repo create` | 创建空仓库供绑定 |
| 绑定远程仓库 | `coze code repo bind` | 仅支持空仓库 |
| 解绑远程仓库 | `coze code repo unbind` | 不删除远程仓库 |
| 推送到远程 | `coze code repo push` | 需先绑定仓库 |
| 拉取远程变更 | `coze code repo pull` | 支持冲突策略 |
| 查看仓库同步状态 | `coze code repo status` | |

## 命令分组

> **执行前必做：** 从下表定位到命令后，务必先阅读对应命令的 reference 文档，再调用命令。

| 命令分组 | 说明 | Reference |
|----------|------|-----------|
| [`project commands`](references/coze-code-project.md) | `create / list / get / delete / import / db list` | 项目全生命周期管理 |
| [`message commands`](references/coze-code-message.md) | `send / status / cancel / history` | 需求发送与状态追踪 |
| [`deploy commands`](references/coze-code-deploy.md) | `deploy / status / list / fix` | 部署、状态查询与失败修复 |
| [`preview`](references/coze-code-preview.md) | `preview` | 沙盒预览链接 |
| [`env commands`](references/coze-code-env.md) | `set / list / delete` | 环境变量(Secrets)管理 |
| [`domain commands`](references/coze-code-domain.md) | `add / list / remove` | 自定义域名管理 |
| [`skill commands`](references/coze-code-skill.md) | `list / add / remove / upload / delete` | 技能管理 |
| [`model commands`](references/coze-code-model.md) | `list / set` | 会话模型管理 |
| [`tools commands`](references/coze-code-tools.md) | `list / enable / disable` | 会话工具管理 |
| [`db commands`](references/coze-code-db.md) | `create / list / get / query / gen-types / dump / rollback / status / delete` | 数据库管理 |
| [`git commands`](references/coze-code-git.md) | `auth login / auth status / auth logout / search` | Git 平台 OAuth 授权与仓库搜索 |
| [`repo commands`](references/coze-code-repo.md) | `create / bind / unbind / push / pull / status` | 远程仓库绑定与同步 |

## 常见错误速查（Code 专用）

> 以下为 Code 专用错误（本节内独立编号 1–7）；基础类错误（认证、`--format json` 等）见根 [`../SKILL.md`](../SKILL.md)。

### 错误 1：把本地路径发给用户

- 问题：`/tmp/...` 只能本机访问，用户无法直接打开。
- 修正：始终执行 `coze file upload`，把上传后的在线 `URL` 发给用户。

### 错误 2：message 仍在 processing 时直接部署

- 问题：项目还没有可部署的代码或 commit，导致部署失败。
- 修正：始终先执行 `coze code message status -p <id> --format json` 确认状态为完成后再部署。

### 错误 3：deploy 命令使用 --project-id 参数

- 问题：`deploy` 命令的项目 ID 是**位置参数**，不是 `--project-id` 选项。
- 修正：使用 `coze code deploy <project-id>` 而非 `coze code deploy --project-id <id>`。

### 错误 4：project create --type 传了不支持的类型

- 问题：`--type` 只接受 `agent | workflow | app | skill | web | miniprogram | assistant`（源码另兼容 `webapp`）；传入其它字符串会报 `E1005 Unknown project type`。
- 修正：从受支持列表中选择类型；常用 `web` / `app`。

### 错误 5：message send 管道输入未加 --stdin

- 问题：`message send` 只有显式传 `--stdin` 才会读取标准输入，否则管道内容被忽略。
- 修正：`cat ctx.txt | coze code message send "..." --stdin -p <id>`。

### 错误 6：db 危险操作未加 --confirm

- 问题：`db query`、`db delete`、`db rollback` 涉及危险操作时必须加 `--confirm`，否则 JSON 模式下报错。
- 修正：始终在执行 DROP/TRUNCATE/DELETE 无 WHERE/UPDATE 无 WHERE 等 SQL 时加 `--confirm`；删除和回滚操作也必须加 `--confirm`。

### 错误 7：数据库未 active 时执行操作

- 问题：数据库处于 `creating` 状态时无法执行 SQL、生成类型或导出 Schema。
- 修正：先执行 `coze code db status --db-id <id>` 确认状态为 `active` 后再操作。
