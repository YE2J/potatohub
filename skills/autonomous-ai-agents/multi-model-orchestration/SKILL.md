---
name: multi-model-orchestration
title: "多模型编排：MOA / Kanban / delegate_task 选型"
description: "根据用户意图选择正确的多模型工具：MOA（圆桌辩论）、Kanban（独立评审）、delegate_task（执行修复）。含三选一决策树、禁止行为、MOA配置指南、provider名称陷阱。"
tags: [multi-agent, routing, moa, kanban, delegation]
---

# 多模型编排

## ⚠️ 用户当前偏好（2026-08 更新）：MOA 为主

用户明确：「简单任务不 delegate 和复杂任务要多agent 的描述已经很少使用了，现在更多是使用 MOA 模式」。
SOUL.md persona 已固化：**深度分析/评审/方案讨论 → 优先 MOA（5参考+聚合器），禁止用 delegate_task 仿真多角色**。
delegate_task 仅在需要独立执行修复/跑脚本时使用。

## 三选一决策树

```
用户要求 → "安排几个agent" → 具体做什么？
  │
  ├─ "评审代码/分析" → Kanban 4张独立卡（GLM/Kimi/MiniMax/Xiaomi）
  │
  ├─ "一起讨论/圆桌/辩论" → MOA（/moa <prompt>）
  │
  ├─ "修复bug/执行操作" → delegate_task
  │
  └─ "先评审再讨论分歧" → Kanban评审 → MOA讨论分歧点
```

## MOA（Mixture of Agents）— 多模型圆桌讨论

**适用场景**：用户说"让不同模型一起讨论""圆桌会议""各自发表意见再汇总""辩论"

**使用方式**：
```bash
hermes moa list           # 查看当前配置
hermes moa configure      # 交互式配置（逐个输入 provider:model，最后选 Done）
/moa <讨论主题>            # 在聊天中触发多模型讨论
```

**原理**：所有参考模型收到同一 prompt **并行输出** → 聚合模型读取所有输出并做：
- 观点提取（每个模型的核心论点）
- 矛盾检测（模型A和模型B的分歧点）
- 共识提取（所有模型一致同意的观点）
- 最终合成（仲裁版结论）

### MOA vs Kanban vs delegate_task 模型路由差异

| 维度 | MOA | Kanban | delegate_task |
|:-----|:---|:-------|:-------------|
| 模型分配 | 配置在 moa.presets，每个槽位独立 provider:model | 每个 profile 有自己的 model/provider | **子agent继承父模型**，多模型需嵌套 profile |
| 参与者本质 | **5个纯模型**，只收文本问题、只回文本观点 | **4个完整 Hermes Agent 进程**（独立会话/记忆/全部工具） | 子 agent 进程，继承父模型 |
| **能否执行工具** | ❌ **参考模型不执行任何工具** — 纯讨论 | ✅ **每个 Worker 能跑 terminal/读文件/写文件/查库/执行代码** | ✅ 子 agent 有工具 |
| 上下文 | 共享同一问题，聚合器综合 5 份回答 | 各自独立上下文，最后汇总 | 各自独立 |
| 产物 | 一份综合观点报告（讨论/评审意见/建议） | 每个 Worker 的真实执行结果（验证过的结论/写好的文件/跑完的数据） | 执行结果 |
| 耗时 | 快（十几秒~1分钟） | 慢（每 Worker 完整 agent 循环，5-15分钟） | 中 |
| 多模型讨论 | ✅ **真实** — 5个不同模型并行，聚合模型仲裁 | ⚠️ 独立工作，无交叉验证 | ❌ 不可能 — 单模型模拟角色 |
| 交互方式 | 一次 `/moa` 触发，自动完成 | 手动创建 N 张卡，`kanban_await` 等完成 | 一次 `delegate_task` 触发 |
| 适用 | **圆桌讨论/交叉验证/仲裁** | **独立评审/各审各的** | **执行修复/跑脚本/查库** |

### ⚠️ 核心决策依据：评审+验证必须 Kanban，MOA 无法替代

- **MOA 参考模型没有工具**——只能给观点，不能给"已验证的执行结果"。
- 用户的 4Agent 评审流程（GLM架构/Kimi逻辑/MiniMax安全/Xiaomi数据）**本质就是 Kanban**，因为评审硬规则要求验证证据（命令输出/行号/数据点），必须真实执行才能产出。
- **判断口诀**：只要观点 → MOA；要"评审+真实验证证据"或"并行执行真任务"（回补数据/并行修 bug/批量回测）→ Kanban。MOA 只能讨论"怎么做"，做不了"真的做"。
- 用户"更多用 MOA"的观察正确——最近任务偏讨论/方案评估；但 4Agent 评审场景 Kanban 仍是唯一解。orchestrator SOUL 应保留，只是按需拉起（平时不占 token）。

### MOA 配置陷阱

| 陷阱 | 现象 | 解决方法 |
|:-----|:-----|:---------|
| `hermes moa configure` **不接受 piped 输入** | `printf '...' | hermes moa configure` 不生效，仍显示旧配置 | 必须交互式手动输入，或用 `hermes config set` / Python regex 直接写 config.yaml |
| `yaml.dump()` 会**破坏 config.yaml** | Python yaml.dump 后 `hermes moa list` 报 YAML 解析错误 | 用纯文本 `sed` 或 Python regex 只替换 moa 段，不要用 `yaml.dump` 回写整个文件 |
| **API Key 不在全局 .env** | Kanban 正常但 MOA 报 "Provider xxx API key not found" | MOA 读全局认证池。worker profile 的 `.env` 不被 MOA 识别。需 `echo "MOONSHOT_API_KEY=$KEY" >> ~/.hermes/.env` |
| Provider 变量名映射 | MOA 配 `moonshot:kimi-k2.6` 但找不到 `MOONSHOT_API_KEY` | 查 worker-kimi/.env 中实际变量名（如 `KIMI_CN_API_KEY`），映射到 MOA 期望的变量名 |
| **Provider 名称写错（最常见）** | 配了 `z.ai` 或 `moonshot`，但 Hermes 根本不识别这两个名字 | 在 MOA 配置中用 `zai`(✓) 而非 `z.ai`(✗)，用 `kimi-coding-cn`(✓) 而非 `moonshot`(✗)。查 `~/.hermes/state-snapshots/*/auth.json` 确认真实 provider 名 |
| **桌面端 `/moa` 命令：可用但补全提示偶缺失** | 桌面 App 输入 `/moa` 可能显示"没有匹配项" | ⚠️ **这是自动补全提示缺失，不是执行失败**（2026-08 实测证伪旧结论）。`/moa` 在后端注册（commands.py:162），桌面端静态命令列表（apps/desktop/src/lib/desktop-slash-commands.ts）虽无 moa 条目，但未知命令走 **extension command 路径**（isDesktopSlashExtensionCommand：不在静态列表 = 扩展命令，后端能处理就允许执行）——所以 `/moa` 一直能执行。**重启 Hermes 后"自愈"**：前端命令索引在启动时重建，重新发现后端命令后补全提示恢复。桌面端另有人口：**左下角模型名 → 模型选择器 → 选 `moa` 虚拟 provider 预设**。会话元数据 "changed to default via provider moa" 即表示已切到 MOA。**教训：静态代码里命令列表缺失 ≠ 不可用，必须先验证运行时执行路径再下结论** |
| **`hermes config set` 嵌套键陷阱** | `hermes config set personalities.pm ...` 写到**顶层** `personalities:`（如 line 708），而原有人格池在 `agent.personalities` 下（line 30），Hermes 读不到 | 嵌套键要写完整路径 `hermes config set agent.personalities.pm ...`。设置后 grep 确认位置；错误写入用 `hermes config unset personalities.pm` 清理。另注意 config.yaml 受保护，不能直接用 patch/write_file 改，必须走 `hermes config` 命令 |

### 配置示例（5 参考模型 + 1 聚合）

```yaml
# ~/.hermes/config.yaml 中 moa 段
moa:
  default_preset: default
  active_preset: default
  presets:
    default:
      enabled: true
      reference_models:
        - provider: deepseek
          model: deepseek-v4-flash
        - provider: zai\n          model: glm-5.1
        - provider: kimi-coding-cn
          model: kimi-k2.6
        - provider: minimax
          model: minimax-m2.7
        - provider: xiaomi
          model: mimo-v2.5
      aggregator:
        provider: deepseek
        model: deepseek-v4-flash
      reference_temperature: 0.6
      aggregator_temperature: 0.4
      max_tokens: 4096
      fanout: per_iteration
```

> ⚠️ **provider 名称精确性**：上例中的 `zai`(✓) 不是 `z.ai`(✗)，`kimi-coding-cn`(✓) 不是 `moonshot`(✗)。如果 MOA 仅 DeepSeek 工作但其他失败，先用下方的诊断命令查真实名称。

### 诊断命令：查 MOA provider 名称

当 MOA 部分模型不工作时，查真实 provider 名：

```bash
cat ~/.hermes/state-snapshots/latest/auth.json | python3 -c "
import json, sys
d = json.load(sys.stdin)
pool = d.get('credential_pool', {})
for p, creds in sorted(pool.items()):
    labels = [c.get('label','?') for c in creds]
    print(f'{p}: {labels}')
"
```

将输出与 `hermes moa list` 的 provider 列逐项比对。

## Kanban — 独立多模型评审

**适用场景**：用户说"安排4个agent评审""审查代码"

**使用方式**：创建 4 张独立卡，详见 `kanban-parallel-review` skill

**关键限制**：Kanban 设计为独立工作，不是辩论。每个 worker 只看自己的维度。

## delegate_task — 执行型多任务

**适用场景**：修复bug、拉数据、改文件、跑脚本

**使用方式**：
```python
delegate_task(tasks=[dict(goal="...", context="..."), ...])
```

**关键限制**：子agent继承父模型，无法实现多模型讨论。

## 🚫 被用户严厉纠正过的错误

| 错误做法 | 正确做法 | 纠正原因 |
|:---------|:---------|:---------|
| `delegate_task(role=orchestrator)` 模拟多模型圆桌 | 用 MOA（`/moa <prompt>`） | 一人分饰多角不是真正的多模型辩论 |
| 用户要求"圆桌讨论"时用 Kanban 线性顺序 | 用 MOA 或 MOA Lite | Kanban 是独立工作，不是交互讨论 |
| 用户要求多模型讨论时用 `delegate_task` | 用 MOA | delegate_task 的子agent继承父模型，不是不同模型 |
| MOA 配置完后不检查 API Key 是否在全局 .env | 先 `grep MOONSHOT_API_KEY ~/.hermes/.env` 确认存在 | worker profile 的 Key 不在 MOA 认证路径上 |
| **MOA 配置了不存在的 provider 名** | 用诊断命令查真实 provider 名 | `z.ai`(✗) 和 `moonshot`(✗) 不是 Hermes 注册名 |

## MOA Lite（当用户没有配置MOA时的后备方案）

如果 MOA 未配置（`hermes moa list` 显示 `(off)`），用两轮 Kanban 模拟：

1. 第一轮：4 张独立卡，**同一问题**，各自输出
2. 读取全部结果后，创建第 5 张卡（选任一 worker）："请阅读以下 4 份观点，做矛盾检测和共识提取"
3. 汇总结果

注意：这不是真正的 MOA（聚合模型只能看到文本输出，不是原生 MOA 管道），但效果接近。
