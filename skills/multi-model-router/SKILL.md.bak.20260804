---
name: multi-model-router
description: 多模型智能路由 v2.0：根据任务复杂度+推理等级自动选择对应 profile（7 个预配置档位），调用 router.py 决策或由 Agent 直接 delegate。
category: autonomous-ai-agents
dependencies:
  scripts: [router.py]
  profiles: [orchestrator, worker-glm, worker-glm-mid, worker-glm-high, worker-kimi, worker-kimi-mid, worker-kimi-high]
---

# 多模型智能路由 v2.0

## 触发条件
用户提出的任务涉及代码生成/测试/分析等场景时，按以下流程处理。

## 工作流程

### 1. 简单任务（≤3 步）→ Agent 直接处理
不需要 load 此 skill，对话中直接回答。

### 2. 中等任务 → dry-run 分析 + 确认
```bash
python3 ~/.hermes/scripts/router.py --task "任务描述" --dry-run
```
查看路由决策后，再决定是直接执行还是 delegate。

### 3. 复杂任务 → delegate 委托
使用 `delegate_task`，在 context 中说明目标 profile。

## 模型版本管理与验证

修改任一 profile 的模型版本后，必须执行完整变更流程。

### 版本变更步骤
1. 改 profile `config.yaml` 中的 `model.default`
2. 更新本 skill 的模型映射表（下表）
3. 更新 memory 中的模型版本记录
4. 全量验证所有 profile

### 全量验证
并行测试所有 profile（快速确认连通性）：
```bash
for p in orchestrator worker-glm worker-glm-mid worker-glm-high worker-kimi worker-kimi-mid worker-kimi-high worker-auditor worker-xiaomi; do
  hermes chat -p "$p" -q "回复OK即可" &
done
wait
```
每个返回 `OK` 即正常。

### 配置陷阱汇总（HTTP 401 排查）
| 现象 | 根因 | 修复 |
|------|------|------|
| `kimi-coding-cn` 有 key 仍 401 | provider 名不被 Hermes 识别 | 改用 `kimi-custom` |
| yaml.dump 后 key 变形 | yaml.dump 重排列序加引号 | 用 patch 或 write_file |
| `.env` vs config key 不同 | 两处 key 不一致 | 保留可用的那个 |
| model 改了 provider 没跟着改 | 只改了模型名 | model.provider 必须匹配 providers 节 |

## 模型映射（9 档）

| 任务类型 | 推理等级 | Profile | 模型 | Provider |
|---------|---------|---------|------|----------|
| 分析/策略/研究 | low/mid/high | orchestrator | deepseek-v4-flash | deepseek |
| 代码生成/实现 | low | worker-glm | glm-5.1 | z.ai |
| 代码生成/实现 | mid | worker-glm-mid | glm-5.1 | z.ai |
| 代码生成/实现 | high | worker-glm-high | glm-5.1 | z.ai |
| 测试/代码审查 | low | worker-kimi | kimi-k2.6 | kimi-custom |
| 测试/代码审查 | mid | worker-kimi-mid | kimi-k2.6 | kimi-custom |
| 测试/代码审查 | high | worker-kimi-high | kimi-k2.6 | kimi-custom |
| 审计/交叉验证/深度分析 | low/mid/high | worker-auditor | minimax-m2.7 | minimax |
| 实现/快速验证/边界条件 | low/mid/high | worker-xiaomi | mimo-v2.5 | xiaomi |

## 推理等级矩阵

| 复杂度 | 无深度关键词 | 有深度关键词 |
|--------|------------|------------|
| simple | low | mid |
| medium | mid | high |
| complex | high | max → high |

## router.py 使用

**干运行（推荐先跑）：**
```bash
python3 ~/.hermes/scripts/router.py --task "任务" --dry-run
```

**自动路由执行：**
```bash
python3 ~/.hermes/scripts/router.py "任务"
```

**手动指定 profile：**
```bash
python3 ~/.hermes/scripts/router.py --task "任务" --profile worker-kimi-high
```

**列出所有可用档位：**
```bash
python3 ~/.hermes/scripts/router.py --list-profiles
```

## 模型版本管理与验证

修改任一 profile 的模型版本后，必须全量验证所有 profile。

### 版本变更步骤

1. 改 profile `config.yaml` 中的 `model.default`
2. 更新本 skill 的模型映射表（上表）
3. 更新 memory 中的 4-Agent 评审阵容版本记录

### 全量验证命令

并行测试所有 profile（快速验证连通性）：

```bash
# 同时启动 9 个 profile 测试
for p in orchestrator worker-glm worker-glm-mid worker-glm-high worker-kimi worker-kimi-mid worker-kimi-high worker-auditor worker-xiaomi; do
  hermes chat -p "$p" -q "回复OK即可，不要多余内容" &
done
wait
```

每个 profile 返回 `OK` 即表示模型版本可正常调用。
⚠️ macOS 没有 `timeout` 命令，用 Hermes terminal 工具的 timeout 参数替代。

### 查看某 provider 的可用模型版本

```bash
source ~/.hermes/.env 2>/dev/null
curl -s https://api.moonshot.cn/v1/models -H "Authorization: Bearer $KIMI_CN_API_KEY"
```

替换 URL 和 key 变量名可查其他 provider（如 z.ai、deepseek 等）。

## 路由规则（14 条正则，具体优先）

1. 编写单元测试/集成测试 → testing
2. 运行测试套件/pytest → testing
3. code review/代码审查/安全审查 → testing
4. 测试覆盖/报告/回归/冒烟/压力 → testing
5. 写代码/创建功能/API → coding
6. 实现算法/排序/搜索/数据结构 → coding
7. 重构/修复/优化代码/bug/性能 → coding
8. 排查/定位 bug → coding
9. 分析/研究/策略/设计/方案/架构 → analysis
10. 市场/行情/股票/估值/财报 → analysis
11. 总结/摘要/归纳 → analysis
12. 解释/说明/对比 → analysis
13. 验证/检查/审查/测试（兜底） → testing

## 注意事项
- ⚠️ **`delegate_task` 无法分配不同模型**：子 agent 继承父模型的 model/provider，所有子任务跑同一个模型（如 deepseek-v4-flash）。需要多模型并行评审时必须使用 **Kanban**（每个 profile 独立配置 model/provider）。详见 `kanban-parallel-review` skill。
- reasoning_effort 由各 profile 的 config.yaml 静态控制
- router.py 的 --reasoning 参数记录决策，实际推理强度取决于所选 profile
- 终端沙箱有 getcwd 权限问题，`hermes --profile` CLI 可能不可用
- 此时回退到 `delegate_task` 机制（但注意只能单模型）
- orchestrator 中高档 profile 待创建
- ⚠️ 自定义 provider 必须配 API Key：仅设 model.provider 不够，还需在 config.yaml 的 providers.<name> 节写入 api_key 和 base_url。否则报 "no API key found"。详见 references/custom-provider-api-key-config.md
- ⚠️ 内置 provider（如 zai）则只认环境变量（ZAI_API_KEY / GLM_API_KEY），写 providers.zai 节没用。修法：设 ~/.hermes/.env。详见 references/custom-provider-api-key-config.md
- ⚠️ **Kimi/Moonshot API Key 配置陷阱**：provider 名 `kimi-coding-cn` 在 profile config 中虽可写，但 Hermes 无法正确解析其 inline API key。即使在 `providers.kimi-coding-cn.api_key` 写了正确 key，仍报 HTTP 401。**修法：改用 `kimi-custom` 作为 provider 名**（已验证可用），在 `providers.kimi-custom` 写入 api_key 和 base_url。详见 references/custom-provider-api-key-config.md
- ⚠️ **避免用 yaml.dump 写 profile config**：Python `yaml.dump()` 会重排 config.yaml 的节顺序、移除注释、可能加额外引号导致 API Key 变形。修法：用 read_file + 编辑特定键值对 + write_file 的方式，或直接用 patch 工具逐项修改。
- v0.17.0 起 delegate_task 强制后台异步执行：不再显示 spinner 和逐任务进度，结果作为独立新消息返回。用 /agents 查看子代理状态，/stop 取消。详见 skill_view(name="dynamic-model-routing", file_path="references/delegate-task-v0.17-background-mode.md")
