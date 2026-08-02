# MiniMax 审计师 — 实操指南

## 速度基准（实测 2026-07-07）

| 派出方式 | 耗时 | 实际模型 | 质量 | 适用场景 |
|---------|------|---------|------|---------|
| `delegate_task` | ~15s | DeepSeek V4 Flash（非 MiniMax） | 基本四维审计，标注「推理受限」 | 日常小审计、快速过一眼 |
| `hermes -p worker-auditor chat` | ~42s | **MiniMax-M3** ✅ | 完整深度审计，含浮点精度、场景分级等高阶分析 | 重要审计：回测报告、跨文件一致性、方案复核 |

## delegate_task 的模型 bug

`delegate_task` **不会**调用 MiniMax-M3。它会硬编码当前会话的主模型（通常是 `deepseek-v4-flash`）。这是 Hermes 的已知 bug（详见 `dynamic-model-routing` skill）。

**结果特征**：审计报告末尾可见 `🔶 基于备选模型完成，推理深度受限` 标注。

## 日常使用推荐

### 方式 A：delegate_task（默认，~15s）

```python
skill_view('minimax-auditor')
delegate_task(goal="全维度审计", context="待审材料")
```

适用于：
- 快速验证 3Agent 评审结果有无明显遗漏
- 数据管线状态检查
- 记忆/skill 一致性检查

### 方式 B：terminal 直调（完整 MiniMax，~42s）

```bash
hermes -p worker-auditor chat -q "审计以下内容，按四维框架输出审计报告：
[粘贴待审材料]"
```

适用于：
- 回测报告深度审计（需要 1M 上下文一次读完所有文件）
- 因子 IC 结果复核（需要 thinking mode 深度推理）
- 跨文件架构一致性审计
- 方案可行性复核（实施前最后一关）

## worker-auditor profile 维护

```bash
# 连通性测试
hermes -p worker-auditor chat -q "只回复OK"

# API key 更新（当 MiniMax 换 key 时）
# .env 从 default profile 继承，更新 default 的 .env 后重新 clone：
hermes profile delete worker-auditor
hermes profile create worker-auditor --clone-from default
```

## 已知风险

1. `delegate_task` 不调用 MiniMax — 如需求 MiniMax 的 1M 上下文和 thinking mode，必须用 terminal 直调
2. worker-auditor 首次启动较慢（~40s 含模型元数据加载），后续调用会更快
