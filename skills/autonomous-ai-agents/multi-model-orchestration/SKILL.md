---
name: multi-model-orchestration
title: "多模型编排：MOA / Kanban / delegate_task 选型"
description: "根据用户意图选择正确的多模型工具：MOA（圆桌辩论）、Kanban（独立评审）、delegate_task（执行修复）。含三选一决策树、禁止行为、MOA配置指南、provider名称陷阱。"
tags: [multi-agent, routing, moa, kanban, delegation]
---

# 多模型编排

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
| 多模型讨论 | ✅ **真实** — 5个不同模型并行，聚合模型仲裁 | ⚠️ 独立工作，无交叉验证 | ❌ 不可能 — 单模型模拟角色 |
| 交互方式 | 一次 `/moa` 触发，自动完成 | 手动创建 N 张卡，`kanban_await` 等完成 | 一次 `delegate_task` 触发 |
| 适用 | **圆桌讨论/交叉验证/仲裁** | **独立评审/各审各的** | **执行修复/跑脚本/查库** |

### MOA 配置陷阱

| 陷阱 | 现象 | 解决方法 |
|:-----|:-----|:---------|
| `hermes moa configure` **不接受 piped 输入** | `printf '...' | hermes moa configure` 不生效，仍显示旧配置 | 必须交互式手动输入，或用 `hermes config set` / Python regex 直接写 config.yaml |
| `yaml.dump()` 会**破坏 config.yaml** | Python yaml.dump 后 `hermes moa list` 报 YAML 解析错误 | 用纯文本 `sed` 或 Python regex 只替换 moa 段，不要用 `yaml.dump` 回写整个文件 |
| **API Key 不在全局 .env** | Kanban 正常但 MOA 报 "Provider xxx API key not found" | MOA 读全局认证池。worker profile 的 `.env` 不被 MOA 识别。需 `echo "MOONSHOT_API_KEY=$KEY" >> ~/.hermes/.env` |
| Provider 变量名映射 | MOA 配 `moonshot:kimi-k2.6` 但找不到 `MOONSHOT_API_KEY` | 查 worker-kimi/.env 中实际变量名（如 `KIMI_CN_API_KEY`），映射到 MOA 期望的变量名 |
| **Provider 名称写错（最常见）** | 配了 `z.ai` 或 `moonshot`，但 Hermes 根本不识别这两个名字 | 在 MOA 配置中用 `zai`(✓) 而非 `z.ai`(✗)，用 `kimi-coding-cn`(✓) 而非 `moonshot`(✗)。查 `~/.hermes/state-snapshots/*/auth.json` 确认真实 provider 名 |

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
