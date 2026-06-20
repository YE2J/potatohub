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

## 模型映射（7 档）

| 任务类型 | 推理等级 | Profile | 模型 |
|---------|---------|---------|------|
| 分析/策略/研究 | low/mid/high | orchestrator | deepseek-v4-flash |
| 代码生成/实现 | low | worker-glm | glm-5.2 |
| 代码生成/实现 | mid | worker-glm-mid | glm-5.2 |
| 代码生成/实现 | high | worker-glm-high | glm-5.2 |
| 测试/代码审查 | low | worker-kimi | kimi-k2.7-code |
| 测试/代码审查 | mid | worker-kimi-mid | kimi-k2.7-code |
| 测试/代码审查 | high | worker-kimi-high | kimi-k2.7-code |

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
- reasoning_effort 由各 profile 的 config.yaml 静态控制
- router.py 的 --reasoning 参数记录决策，实际推理强度取决于所选 profile
- 终端沙箱有 getcwd 权限问题，`hermes --profile` CLI 可能不可用
- 此时回退到 `delegate_task` 机制
- orchestrator 中高档 profile 待创建
