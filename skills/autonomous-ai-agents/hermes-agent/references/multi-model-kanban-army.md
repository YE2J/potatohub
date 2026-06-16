# 多模型 Kanban 军团搭建流程

将多个 LLM provider 的模型注册为 Hermes profile worker，通过 Kanban 看板系统实现任务自动分发。

## 前置条件

- 各 provider 的 API key 已写入 `~/.hermes/.env`
- Gateway 已启动（`hermes gateway start`，kanban dispatcher 内嵌在 gateway 中）
- `kanban.orchestrator_profile` 指向一个可用的 orchestrator profile
- `kanban.auto_decompose: true`，`kanban.dispatch_in_gateway: true`

## 搭建步骤

### 1. 确认 API Key 和模型可用性

```bash
hermes auth list                          # 查看已注册的 credential 及状态
```

每个 provider 的 API key 状态：`←` 表示就绪，`auth failed` 表示需要更新。

### 2. 创建 worker profile

```bash
# 从一个已知可用的 profile 克隆（保留 skills、.env 等）
hermes profile create worker-<name> --clone-from worker-kimi

# 设置 provider 和模型
hermes config set model.provider <provider> --profile worker-<name>
hermes config set model.default <model-name> --profile worker-<name>

# 清除可能残留的错误 base_url
hermes config set model.base_url '' --profile worker-<name>
```

### 3. 编写身份标识 (SOUL.md)

为每个 worker 赋予独特的身份和专长领域，便于 orchestrator 智能分配任务：

```bash
# 编辑 ~/.hermes/profiles/worker-<name>/SOUL.md
```

SOUL.md 应包含：身份名称、专长领域、风格、工作准则。

示例分工参考：
- **智谋**（推理/数据分析）→ GLM-4-Plus
- **卷王**（长文档/深度研究）→ Kimi K2.6
- **军师**（创意/策略规划）→ Qwen-Plus
- **工匠**（代码实现/性能优化）→ DeepSeek V4 Pro

### 4. 验证连接

```bash
hermes -p worker-<name> chat -q "只回复两个字：就绪"
```

常见错误：
- **401** — API key 无效或过期，需要更新
- **404 model not found** — 模型名不对，尝试 provider 支持的其他模型名

### 5. 初始化 Kanban 看板

```bash
hermes kanban init
```

输出会列出所有可用 profile。Gateway 的 dispatcher 每 60 秒扫描一次 `ready` 状态的任务。

### 6. 端到端测试

```bash
# 用 orchestrator 分解一个测试任务
hermes -p orchestrator chat -q "请将以下任务分解并分配给合适的worker：任务：分析A股市场最近一周的走势，并给出下周投资建议。"
```

验证流程：
```bash
hermes kanban list          # 看任务状态
sleep 65 && hermes kanban list  # 等 dispatcher 调度后再次查看
```

`ready` → `running` 表示 dispatcher 已自动启动 worker 执行任务。

## 注意事项

- 不要手动设置 `base_url` 指向错误的 provider API 端点（如 GLM worker 的 base_url 指向 DeepSeek）
- Qwen/DashScope 的 `dashscope` 和 `alibaba-coding-plan` provider 都指向国际端点 `dashscope-intl.aliyuncs.com`，国内 key 可能不兼容
- NVIDIA NIM 的模型名需精确匹配，常见可用模型：`meta/llama-3.1-70b-instruct`、`mistralai/mistral-large-2-instruct`
- 如果 NVIDIA key 有效但模型不可用，可退回到 DeepSeek 等已确认可用的 provider
