---
name: multi-model-orchestration
title: "多模型编排：MOA / Kanban / delegate_task 选型"
description: "根据用户意图选择正确的多模型工具：MOA（圆桌辩论）、Kanban（独立评审）、delegate_task（执行修复）。含三选一决策树、禁止行为、MOA配置指南、provider名称陷阱。"
tags: [multi-agent, routing, moa, kanban, delegation]
version: 1.1.0
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
  ├─ "评审代码/分析" → Kanban 6张独立卡（5 worker + 1 orchestrator）
  │
  ├─ "一起讨论/圆桌/辩论" → MOA（/moa <prompt>）
  │
  ├─ "修复bug/执行操作" → delegate_task
  │
  └─ "先评审再讨论分歧" → Kanban评审 → MOA讨论分歧点

## Agentic 量化任务：五阶段覆盖检查（论文 2608.31041）

> 依据：`Agentic Quantitative Trading: A Survey of Workflows, Systems, and Evaluation`（arXiv 2608.31041，2026-08-31；综述 2025–2026 文献，含 20 个系统 + 15 个基准）。在编排任何"多模型评审/执行量化任务"前，先做覆盖检查再选型，避免用低层级验证结论支撑跨层断言。

**五阶段管线（落点定位用）：**
因子挖掘（factor mining）→ 信号发现（signal discovery）→ 组合构建（portfolio construction）→ 订单执行（order execution）→ 风控（risk management）。

**基准四分类（验证强度递增，须与能力声明一一对应）：**

| 基准类别 | 验证什么 | 论文中的代表 |
|:--|:--|:--|
| 策略构建 strategy construction | alpha 公式质量；交易意图能否转成可执行代码/结构化策略 | AlphaEval 类公式评测、意图→策略翻译 |
| 离线交易 offline trading | 历史数据/模拟市场上做决策的收益 | StockBench 类历史回测（需受控） |
| 实盘 live market evaluation | 真实市场条件下的收益 | DeepFund、Agent Market Arena、PolyBench |
| 可靠性 reliability assessment | 收益是否可信：泄露 / 误导信息 / 收益归因 | Profit Mirage(FinLake-Bench)、AutoRedTrader、KTD-FIN |

**综述三条实证结论（编排时的默认前提）：**

1. **系统过度集中在信号发现，组合/执行/风控集成不足**：20 个被审系统全部把信号发现当核心功能；因子挖掘仅 4 个、组合构建 8 个、订单执行 3 个、风控 9 个当核心；只有 4 个至少部分覆盖全部五阶段、只有 2 个把五阶段全当核心。→ 市面上的"量化 agent"方案默认只解决信号发现，把"能选出信号"说成"能赚钱"是结构性外推错误。
2. **多 agent 高度依赖聚合**：17 个多 agent 系统中 15 个靠聚合各 agent 输出做最终决策（selection 仅 5、debate 3、gating 2）。→ 聚合只做"观点合成"，不回答"哪个 agent 该信、何时该阻止动作"。对应本 skill：MOA 是聚合型（纯观点）、Kanban 是独立执行+验证型——**观点聚合永远不能替代执行验证**，把 MOA 输出当"已验证结论"是错误用法。
3. **强模型 ≠ 强业绩**：所有实盘基准都显示真实收益取决于模型能力之外的 风控、系统设计、流动性、滑点（Agent Market Arena 发现 agent 架构比 LLM 骨干解释更多业绩差异；PolyBench 发现高预测精度+高置信度不保证盈利）；3 个可靠性基准全部显示 时序泄露、误导信息、收益归因不清 会改写业绩解释（KTD-FIN 分离市场暴露/风格暴露/选股效应）。→ 回测收益 ≠ 实盘能力；模型聪明 ≠ 业绩可信。

**编排前检查（3 步，量化相关评审/执行任务必做）：**

1. **落点定位**：任务主产物落在五阶段哪一段？在任务声明中写清"本任务覆盖：信号发现"等，禁止把单阶段结论外推到未覆盖阶段。例：评审某选股模型 → 落点 = 信号发现（+组合构建的资产选择），别用因子 IC 当"能稳定盈利"的证据；评审下单/风控逻辑 → 落点 = 执行/风控，别用信号准确率当执行质量证据。
2. **基准匹配（四分类对应四档证据，禁止跨类外推）**：
   - "策略能写出来 / 公式质量" → 策略构建档证据；
   - "离线回测赚" → 离线档证据，且必须过泄露控制（时间/标的信息分离、暴露归因，参照 KTD-FIN、Profit Mirage 口径），评审验收卡里写明用了哪种控制；
   - "实盘能赚 / 实盘可信" → 才允许引用实盘档（须含成本、滑点、流动性口径，参照 PolyBench/DeepFund）并附可靠性档检查（泄露/误导/归因）。
   - 评审报告中的每个业绩断言都要标注它属于哪一档证据；拿不出对应档位 → 该断言降级为"假设"。
3. **编排联动（与本 skill 三选一决策树衔接）**：
   - 落点在 因子挖掘/信号发现 的讨论、找思路、观点分歧 → **MOA** 合适，但产物定性为"候选观点"，必须再落 **Kanban** 执行验证（因子 IC、分层回测、防未来信息），Kanban 卡的验收标准须含对应基准档位；
   - 落点在 组合/执行/风控，或任何要求"执行结果可信"的任务 → 直接 **Kanban**（每个 worker 带验证证据），聚合不是验证；
   - 任务横跨 ≥3 个阶段 → 按阶段设 gate 逐段过，并把后阶段结果（执行滑点、风控触发）反馈修正前阶段信号——综述指出的完整工作流缺口正是"前段信号不接后段执行"。
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
| 参与者本质 | **5个纯模型**，只收文本问题、只回文本观点 | **6个完整 Hermes Agent 进程**（5 worker + 1 orchestrator，独立会话/记忆/全部工具） | 子 agent 进程，继承父模型 |
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
- **MOA→Kanban 转化（2026-09-01 用户确认）**：MOA 聚合输出必须细化成 Kanban 执行卡的工作任务+工作目标，每卡目标/验收标准须能溯源到 MOA 条目；Kanban 执行严格以 MOA 方案为基准，执行中发现关键偏差（影响验收/目标/关键路径）→ 暂停整个任务 → 如实汇报+建议 → 等用户裁决（重 MOA 或按建议更新方案）。详见 standard-task-lifecycle Stage 3 执行偏差处理协议。
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
| **`hermes config set` 嵌套键陷阱** | `hermes config set personalities.pm ...` 写到**顶层** `personalities:`（如 line 708），而原有人格池在 `agent.personalities` 下（line 30），Hermes 读不到 | 嵌套键要写完整路径 `hermes config set agent.personalities.pm ...`。设置后 grep 确认位置；错误写入用 `hermes config unset personalities.pm` 清理。另注意**顶层** `~/.hermes/config.yaml` 受保护不能 patch，但 `profiles/<name>/config.yaml` 可以用 `patch` 直接改（改前备份） |
| **profile 里的 MOA preset 删不掉** | `hermes moa delete default` 报 `Cannot delete the only MoA preset`；把 `moa` 段整段删掉后 `hermes moa list` 仍显示 gpt-5.5/opus 参考席 | 那不是你的配置，是 Hermes **内置默认 preset**（`hermes_cli/moa_config.py` 的 `DEFAULT_MOA_REFERENCE_MODELS` / `DEFAULT_MOA_AGGREGATOR`），空 `presets` 会被 `_normalize_preset` 重新填充。删不掉只能**禁用**：profile config 写 `presets: {default: {enabled: false, reference_models: []}}` + `default_preset: ''`。禁用后 `hermes moa list` 依旧打印内置参考席（显示层填充），**以 `hermes -p <p> config get moa` 为准**。完整配方见 `references/moa-preset-lifecycle.md` |

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
