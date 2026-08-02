# delegate_task v0.17.0 行为变更：强制后台模式

## 变更概要

Hermes v0.17.0 起，**顶层 `delegate_task` 调用强制后台异步执行**。

代码位置：`run_agent.py` → `_dispatch_delegate_task()` (L5327-5350)

```python
# Delegations from the top-level MODEL always run in the background —
# the model does not get to choose.
background=(not _is_subagent),  # _delegate_depth==0 → background=True
```

## 行为对比

| 维度 | v0.16.x 及之前 | v0.17.0+ |
|------|--------------|----------|
| 执行模式 | 同步阻塞（parent 等待） | 强制后台异步 |
| 进度显示 | spinner + 逐任务完成行 `✓ [1/3] ... (12s)` | 仅返回 `{"status":"dispatched"}` |
| 结果返回 | inline，随 tool response 一起 | 作为**独立新消息**稍后插入对话 |
| parent 行为 | 等待所有子代理完成后继续 | 立即继续，不等待 |

## 对 workflow 的影响

### 之前的体验
```
用户: 做任务A、B、C
Agent: [delegate_task batch]
       ⠋ 处理中...
       ✓ [1/3] 任务A (12s)
       ✓ [2/3] 任务B (8s)
       ✓ [3/3] 任务C (15s)
Agent: 三个任务都完成了，结果如下...
```

### 现在的体验
```
用户: 做任务A、B、C
Agent: [delegate_task → 返回 "dispatched"]
Agent: 已派发3个子代理，结果稍后返回。
       （此时可以继续其他工作）

--- 一段时间后，新消息出现 ---
[子代理结果] 任务A/B/C 的汇总...
```

## 监控子代理状态

- **`/agents` 命令**：查看活跃子代理列表
- **TUI 状态栏**：配置 `display.tui_agents_nudge: true` 时显示 ⛓ 标记
- **`/stop` 命令**：取消所有运行中的后台子代理

## 例外情况

Orchestrator 子代理（`_delegate_depth > 0`）调用 delegate_task 时**仍然同步执行**，因为子代理需要 workers 的结果来合成自己的 summary，且没有独立的 gateway session 接收异步结果。

## 相关配置

```yaml
delegation:
  max_concurrent_children: 3   # 单次 delegate_task 最大子代理数
  max_async_children: 3        # 后台异步池容量
  child_timeout_seconds: 600   # 子代理超时
```
