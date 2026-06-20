# code project commands

> **前置条件：** 先阅读 [`../../SKILL.md`](../../SKILL.md) 了解认证、全局参数和安全规则。

项目管理相关命令索引。涵盖项目的创建、列表查询、详情获取、删除、导入和数据库表查看。

## 命令导航

| 文档 | 命令 | 说明 |
|------|------|------|
| 本文档 | `coze code project create` | 创建新项目 |
| 本文档 | `coze code project list` | 列出项目（支持按类型/名称筛选） |
| 本文档 | `coze code project get <id>` | 查看项目详情 |
| 本文档 | `coze code project delete <id>` | 删除项目（不可逆） |
| 本文档 | `coze code project import` | 从远程仓库或本地 zip 导入项目 |
| 本文档 | `coze code project db list -p <id>` | 列出项目数据库表 |

> 注意：所有命令均需先完成认证和组织/空间上下文配置。别名 `coze code proj` 可替代 `coze code project`。

---

## project create

创建新的 Coze Coding 项目（通过自然语言描述生成项目结构）。

### 参数

| 参数 | 必填 | 说明 |
|------|------|------|
| `--message` | 是 | 项目描述或需求文本（**无 `-m` 短别名**） |
| `--type` | 是 | 项目类型：`agent` / `workflow` / `app` / `skill` / `web` / `miniprogram` / `assistant`（源码另兼容 `webapp`） |
| `--wait` | 否 | 等待项目创建完成（含首次 AI 响应） |
| `--chat-mode` | 否 | 对话模式：`ask` / `agent` / `dangerous_confirm` / `plan` |
| `--model-name` | 否 | 项目使用的模型名 |
| `--tool-name` | 否 | 启用的工具名（可多次传入） |
| `--design` | 否 | 启用设计向导（`--chat-mode plan` 时自动开启） |
| `--org-id` / `--space-id` | 否 | 组织/空间 ID（缺省读取上下文） |
| `--format` | 否 | 输出格式，默认 `text` |

### 推荐命令模板

```bash
# 创建 Web 项目（最常用）
coze code project create --message "创建一个聊天机器人" --type web --format json

# 创建 App 项目
coze code project create --message "移动端应用" --type app --format json

# 等待创建完成（含首次 AI 响应）
coze code project create --message "电商网站" --type web --wait --format json
```

### 项目类型识别（按"产品形态"判定）

创建前**必须**先根据用户意图选准 `--type`，**不要默认 `web`**。

> **核心原则：决定 `--type` 的是用户描述的「产品形态 / 载体」（小程序 / App / 网页 / 智能体 …），而非「功能品类」（抽奖 / 商城 / 聊天 / 投票 …）。功能词只说明"做什么"，不改变类型。** 先找形态词，命中即定型并忽略功能词干扰；无任何形态词、只有功能描述时才反问，不要擅自默认 `web`。

| 形态词（出现即命中，可带任意功能前缀） | 推荐 `--type` |
|------------------|--------------|
| "小程序 / 微信小程序"（如 抽奖小程序 / 商城小程序 / 点餐小程序 / 预约小程序） | `miniprogram` |
| "App / 应用 / 移动端应用 / 手机 App / 原生应用" | `app` |
| "网页 / 网站 / Web 页面 / 落地页 / 官网 / H5" | `web` |
| "智能体 / Agent / 机器人 / 客服 bot" | `agent` |
| "工作流 / 自动化流程" | `workflow` |
| "技能 / skill 插件" | `skill` |
| "助手 / assistant" | `assistant` |

判定要点：
- **「小程序」是强信号**：只要出现"小程序"三字，一律 `--type miniprogram`，**绝不**因前面带"抽奖 / 商城 / 聊天"等功能词归成 `web`。例："做一个抽奖小程序" → `--type miniprogram`（✗ 不是 `web`）。
- **「App / 应用」**（而非"网页 / 网站 / 页面"）一律 `--type app`；仅"Web 应用 / 网页应用"才用 `web`。
- 多个形态词冲突或完全无形态词（如"做个商城"）时**先反问**，确认后再创建。

### 返回值

`--format json` 时返回 `{ project_id, type, project_url }`：
- `project_id`：**务必记录**，供后续 message/deploy/preview 使用。
- `project_url`：CLI 已按平台生成好的项目对话页面链接，**直接读取此字段透传给用户，不要自行拼接**。

### 创建成功后的回复要求

- **默认不触发部署**：`project create` 只完成项目创建与首次 AI 开发，**绝不**自动 `deploy`；部署须等用户明确要求且 `message status` 为 `done`。
- **必须附上「打开项目」入口**：回复中给出 CLI 返回的 `project_url`，方便用户直接跳转到项目对话页面，省去在项目列表 / 历史会话中二次查找。
  - `project_url` 由 CLI 按**项目类型**自动生成（`web` / `app` / `miniprogram` 为 `https://www.coze.cn/p/<project_id>`；其它类型为 `https://code.coze.cn/p/<project_id>`），**优先直接使用该字段**。
- **必须主动跟进到开发完成**：创建后不能停在"正在开发中"。查询状态**优先主动轮询** `coze code message status -p <project_id>` 直到 `done`（`--wait` 仅备选），不要让用户自己查状态。
- **开发任务完成后**（轮询到 `done`）给出后续引导：继续开发（`message send`）、部署应用（`deploy`，需要时再执行）、打开项目（`project_url`）。
  - **「预览效果」一行仅 `web` 类型显示**：当 `--type web` 时，先执行 `coze code preview <project_id> --format json` 取回 `preview_url`，把预览地址**直接展示**给用户（沙盒初始化需 1-3 分钟，未就绪可重试一次）；非 `web` 类型（`app` / `miniprogram` / `agent` / `workflow` / `skill` / `assistant`）**省略整行**，不展示预览地址。

### 创建失败时的回复

当 `project create` 失败（如报错、未返回 `project_id`、上下文缺失等）时，**不要**只把原始错误堆栈丢给用户，按以下模板友好提示并引导用户补充信息后重试：

```
项目创建失败
你可以重新发起创建，或补充更明确的项目类型、页面需求和目标空间后再试。
```

### 坑点

- **`--type` 仅接受受支持列表内的值**，传入未知类型报 `E1005 Unknown project type`；`web` / `app` 最常用，`assistant` 走模板复制创建。
- `--message` 没有 `-m` 短别名，必须写全。
- 不带 `--wait` 时命令会立即返回 project_id，但首次 AI 消息仍在后台处理中。
- `web` / `app` / `miniprogram` 三种类型默认以 **Coze 3.0 方式**创建；其它类型使用原有创建方式。
- 项目访问域名由**项目类型**决定（`web` / `app` / `miniprogram` 为 `www.coze.cn`，其它类型为 `code.coze.cn`）；`COZE_CLI_PLATFORM` 仅在无法获知类型时作回退，详见 [`../../SKILL.md`](../../SKILL.md) 的「环境变量覆盖」。

---

## project list

列出当前组织和空间下的项目。

### 参数

| 参数 | 必填 | 说明 |
|------|------|------|
| `--type` | 否 | 按类型筛选（可多次传入）：`agent` / `workflow` / `webapp` / `app` / `skill` / `web` / `miniprogram` / `assistant`（无效值会被静默忽略） |
| `--name` | 否 | 按名称搜索 |
| `--size` | 否 | 返回数量（默认 10） |
| `--cursor-id` | 否 | 分页游标 |
| `--has-published` | 否 | 按发布状态筛选 |
| `--search-scope` | 否 | 创建者范围：0=全部 / 1=我创建 / 2=含协作者 |
| `--folder-id` | 否 | 按文件夹筛选 |
| `--order-type` | 否 | 排序方式：0=降序 / 1=升序 |
| `--order-by` | 否 | 排序字段：0=updated_at / 1=created_at |
| `--is-fav-filter` | 否 | 仅看收藏 |
| `--format` | 否 | 输出格式，默认 `text` |

### 推荐命令模板

```bash
coze code project list --format json
coze code project list --type web --format json
coze code project list --name "客服" --format json
coze code project list --type agent --type workflow --format json
```

---

## project get

获取单个项目的详细信息。

| 参数 | 必填 | 说明 |
|------|------|------|
| `<project-id>` | 是 | 项目 ID（位置参数） |
| `--format` | 否 | 输出格式，默认 `text` |

```bash
coze code project get <project-id> --format json
```

---

## project delete

删除指定项目。**无 `--confirm` 选项，执行即删除，不可逆。**

| 参数 | 必填 | 说明 |
|------|------|------|
| `<project-id>` | 是 | 项目 ID（位置参数） |

```bash
coze code project delete <project-id>
```

### 注意事项

- **不可逆操作**，执行前确认用户意图。
- 用户已明确要求删除且目标明确时可直接执行。

---

## project import

从远程 GitHub 仓库或本地 zip 文件导入创建新项目。

### 参数

| 参数 | 必填 | 说明 |
|------|------|------|
| `-s` / `--source` | 是 | 导入来源：`github` / `local` |
| `-r` / `--repo` | 条件必填 | 远程仓库全名（如 `user/repo`），`--source github` 时必填 |
| `-f` / `--file` | 条件必填 | 本地 zip 路径（最大 500MB），`--source local` 时必填 |

### 推荐命令模板

```bash
# 从 GitHub 导入
coze code project import -s github -r user/my-app --format json

# 上传本地 zip
coze code project import -s local -f ./project.zip --format json
```

### 返回值

`--format json` 时返回：

| 字段 | 说明 |
|------|------|
| `project_id` | 新建项目 ID |
| `source` | 导入来源（`github` / `local`） |
| `repo` | 源仓库全名（仅 `github` 导入时返回） |
| `project_url` | 项目 Web 地址，可直接给用户 |

### 坑点

- 远程导入需先完成 OAuth 授权（`coze code git auth login`），导入后会自动绑定到源仓库。
- 本地文件必须是 `.zip` 且不超过 500MB。
- 导入成功后，CLI 会自动在后台向项目默认会话发送初始化 query（「按标准流程初始化当前项目」，对齐 Web 端行为），可用 `coze code message status -p <project_id>` 跟进初始化进度；发送失败不影响导入结果，可手动补发 `coze code message send "按标准流程初始化当前项目" -p <project_id>`。

---

## project db list

列出项目的数据库表（遍历 `knowledge` 和 `public` 两个 schema）。

### 参数

| 参数 | 必填 | 说明 |
|------|------|------|
| `-p` / `--project-id` | 是 | 项目 ID |
| `--env` | 否 | 环境：`dev`（默认）/ `prod`（仅 `prod` 生效，其它值回退 dev） |
| `--schema` | 否 | 声明存在但当前实现忽略该参数，始终返回两个 schema 的表 |

```bash
coze code project db list -p <project-id>
coze code project db list -p <project-id> --env prod
```
