---
name: kanban-parallel-review
description: 4-agent parallel review via Kanban dispatch.
version: 1.4.0
author: Hermes
metadata:
  hermes:
    tags: [Kanban, CodeReview, MultiAgent, Quality]
---

# Kanban Multi-Model Parallel Review

Dispatch 3-4 specialized Worker profiles (different LLMs) through Kanban to review code or proposals in parallel, then have an orchestrator synthesize the results. Handles worker failures with automatic retry and fallback paths.

This is the audit-and-fix cycle pattern, distinct from the broader review-driven-execution loop: focused on the dispatch → collect → classify → fix → re-verify workflow.

**Does NOT cover**: initial Kanban profile setup (see `kanban-worker-fleet`), or the full RDE lifecycle (see `review-driven-execution`).

## When to Use

- User says "安排4个agent" or "安排4个agent去评审"
- Code was drafted and needs quality review (architecture + logic + performance)
- A proposal/analysis needs multi-perspective evaluation
- A previous review cycle found issues and you want to verify fixes
- The task has 3+ independent evaluation dimensions

## ⚠️ 必须包含所有可用 Worker（重要）

当用户要求"安排4个agent评审"时，必须创建 **所有可用 worker profile 的卡**，包括：

| Profile | Model | 角色 |
|---------|-------|------|
| `worker-glm` | GLM-5.1 | 架构/代码组织 |
| `worker-kimi` | Kimi K2.6 | 逻辑/边界条件 |
| `worker-minimax` | MiniMax M2.7 | 性能/安全/运维 |
| `worker-xiaomi` | MiMo v2.5 | 数据完整性/漏检补充 |
| `worker-qwen` | Qwen3.7-Plus | 方案论证/综合分析/行业研究 |

**然后**创建 orchestrator（DeepSeek V4 Flash）做汇总合成。

总计 = 5 worker + 1 orchestrator = **6张卡 / 6个不同模型**。

> 这是用户反复强调的要求（跨多个对话），不能只派3个worker。忘记包含 `worker-xiaomi` 是已被纠正过的错误，`worker-qwen` 于 2026-08-22 加入阵容。

## Prerequisites

- Kanban initialized: `hermes kanban list` works
- Gateway running: `hermes gateway status` shows PID
- Worker profiles exist (`worker-glm`, `worker-kimi`, `worker-minimax` at minimum) with valid API keys
- orchestrator profile exists with `kanban` in its `platform_toolsets.cli`
- `~/.hermes/config.yaml` has `kanban.orchestrator_profile: orchestrator`, `kanban.auto_decompose: true`, `kanban.dispatch_in_gateway: true`

## How to Run

Use `kanban_create` from the default profile to dispatch 3 worker cards, then a synthesis card. Wait for gateway to pick them up (every 60s by default), then `kanban_show` to read completed results.

## Quick Reference

```bash
hermes kanban create "<title>" --assignee worker-glm --body "..."
hermes kanban create "<title>" --assignee worker-kimi --body "..."
hermes kanban create "<title>" --assignee worker-minimax --body "..."
hermes kanban create "<title>" --assignee worker-xiaomi --body "..."
hermes kanban create "<title>" --assignee worker-qwen --body "..."
hermes kanban list                              # Wait for all 5 to reach 'done'

# 自动推送（注意: kanban_await.py 只支持 --timeout 和 --interval，不支持 --extra-ticks）
# 建议放到 terminal(background=true, notify_on_complete=true) 中运行
cd ~/my_quant_system && python3 scripts/kanban_await.py t1 t2 t3 t4 t5 --timeout 600

# orchestrator合成卡：不带--parent
hermes kanban create "<title>" --assignee orchestrator --body '请汇总以下评审结果：\n1) TASK_ID_GLM (worker-glm: 架构)\n2) TASK_ID_KIMI (worker-kimi: 逻辑)\n3) TASK_ID_AUDITOR (worker-minimax: 性能安全)\n4) TASK_ID_XIAOMI (worker-xiaomi: 数据完整)\n5) TASK_ID_QWEN (worker-qwen: 方案论证/综合分析)\n用 kanban show 读取各卡。对 done 卡汇总，对 failed/crashed/超时todo 标记【不可用】。\n输出分类(🔴/🟡/🟢)和矛盾仲裁。'
hermes kanban show <task_id>                    # Read handoff
hermes kanban archive <task_id>                 # Clean up
```

## ⚡ 派发频率

Gateway 默认 60s 派发一次。可改 config.yaml 的 `kanban.dispatch_interval_seconds: 15` 加速（需重启 gateway 生效）。
重启方式：从 gateway **外部的终端窗口**执行 `hermes gateway restart`（从当前 gateway 进程内无法重启，SIGTERM 传播问题）。

## 🧠 delegate_task vs Kanban：模型路由区别

这两种方式都支持「并行派发」，但模型路由机制完全不同：

| 维度 | delegate_task | Kanban (profile-based) |
|:-----|:-------------|:-----------------------|
| **模型分配** | **子agent继承父模型的配置**（当前profile的model/provider） | **每个profile有独立模型配置**（worker-glm=GLM, worker-kimi=Kimi, worker-minimax=MiniMax, orchestrator=DeepSeek）|
| **实现多模型** | ❌ 不能，除非层层嵌套不同profile（不支持） | ✅ 天然支持，每个worker配不同LLM |
| **后台独立性** | ✅ 独立进程，各自在后台跑 | ✅ 独立进程，gateway调度 |
| **parents死锁** | ✅ 无parents概念，不会死锁 | ⚠️ 用parents会死锁，已改为无parents模式 |
| **适合场景** | 需要混合操作的fix任务（跑脚本+查库+改文件） | 纯评审/分析任务（读+写结论） |

**因此：`delegate_task` 跑不出来不同模型的评审。** 用户要求4个不同模型评审时，只能用 Kanban。反过来，修复任务用 `delegate_task` 更灵活。

## 📢 User Communication（重要，多次被纠正）

**Kanban 卡完成后不会自动通知当前对话。** 这是系统设计限制（no auto-notify）。

### 🔴 关键：kanban_await.py 后台输出不会自动推送到对话

`kanban_await.py` 在后台（`terminal(background=true)`）运行时，其 stdout 缓冲在进程日志中，
**不会自动推送到对话中**。即使使用 `notify_on_complete=true`，也只收到进程退出的通知（且输出较长时会被截断只显示最后一段），输出内容不会回到对话。

```bash
# 这个命令的输出不会回到对话！
python scripts/kanban_await.py t1 t2 t3 --timeout 600 &
```

**必须在同一回合立即设置主动轮询**：

```python
# 创建卡 + 启动 kanban_await 后，立即开始轮询
process(action='poll', session_id='proc_xxx')  # 每30秒检查一次
# 当 status=exited 时，process(action='log') 读取完整输出
# 输出中包含每个已完成卡的摘要
```

或者更直接地绕过 `kanban_await.py`，直接用 `hermes kanban list` 每30秒检查：

```python
# 方案A：使用 kanban_await.py（需配合主动poll）
result = terminal("cd ~/my_quant_system && python3 scripts/kanban_await.py t1 t2 t3 --timeout 600 &")
bg_id = extract_session_id(result)
# 立即设置监控
check = process(action='poll', session_id=bg_id)

# 方案B：手动轮询（更可靠）
sleep(30)
result = terminal("hermes kanban list | grep -E 'card1|card2|card3'")
# 解析状态...
```

### 禁止行为

- 创建 `kanban_await.py` 后台进程后不设轮询，等用户问"卡死了吗" — 这是被用户严厉纠正过的
- 全部完成但一直不创建orchestrator汇总，等用户催"为什么还没汇总"
- 完成的结果不主动呈现，等用户问"进度如何"

### 必须行为

1. **创建卡后立即启动 `kanban_await.py`** 自动轮询
2. **同时立即开始 `process(action='poll')` 监控** — 后台输出不会自动回来
3. **全部完成时立即创建orchestrator汇总** — 不等用户催
4. **结果回来后自动呈现摘要** — 不等用户问
5. **完事后主动问"要安排4个agent评审这个吗"** — 用户明确说过"做完一件任务就评审任务质量和排查bug"

### Communication模式

```
创建卡 → kanban_await.py启动 → 告知"完成后自动推送"
    → 完成时自动打印摘要 → 创建orchestrator
    → 自动打印汇总 → 呈现给用户 → 主动问"要评审吗"
```

**整个流程不需要用户参与轮询。一旦创建完卡，用户可以在对话中消失，结果会自己回来。**

### 创建卡后的通信规则

1. **创建卡后立即告知用户**卡ID、分配模型、预计等待时间
2. **主动轮询，不等用户催**：`hermes kanban list` 每30-60秒检查一次
3. **进度变化时主动汇报**：完成一个就告诉用户一个
4. **全部完成时才创建汇总卡**：不等用户问"为什么没汇总"

### 实测等待时间参考（15s dispatch interval）

| Worker | 模型 | 一般耗时 | 备注 |
|--------|------|:--------:|------|
| `worker-glm` | GLM-5.1 | ~3-5min | 通常最快 |
| `worker-kimi` | Kimi K2.6 | ~5-9min | 第二快，但容易卡在 running 状态超10分钟 |
| `worker-minimax` | MiniMax M2.7 | ~6-8min | 最慢但评审最详细 |
| `worker-xiaomi` | MiMo v2.5 | ~4-9min | 2026-07-12新加入。通常3-5分，但复杂评审可达9分。接近600s超时时需使用 `--timeout 900` 加长超时 |
| `worker-qwen` | Qwen3.7-Plus | ~2-5min | 2026-08-22加入阵容。带原生推理，输出质量高；首调含冷启动可能偏慢 |
| `orchestrator` | DeepSeek V4 Flash | ~30-60s | 汇总卡极快 |

**典型总等待**: ~5-10分钟（5 worker + 1 orchestrator）

### ⚡ 卡住检测与降级决策

当大部分 worker 已完成但个别仍显示 running 超预期时间时：

**检测方法**：
```bash
hermes kanban show <task_id>   # 检查详细状态：实际是否在运行，还是挂着？
```

**降级决策触发条件**：
- 已过去时间 ≥ 该 worker 最大预期时间 × 1.5
- 且 已有 ≥ 4/5 的 worker 已完成 (done)
- 或 用户主动问"卡住了吗"

**降级操作**：
1. 跳过卡住的 worker，用已完成的结果创建 orchestrator 汇总卡
2. 告知用户：`{worker名} 超时未完成，已跳过，用其余3家结论汇总`
3. 不删除卡住的卡 — 它可能在后台自己完成，但不等了
4. 如果用户回复后它突然完成，可用 `kanban show` 补充读取

### 主动轮询模式

```python
# 创建后立即告知用户
print(f"已派出: {t1}(GLM) {t2}(Kimi) {t3}(MiniMax)，预计3-10分钟")

# 主动轮询而不是等用户问
sleep(90)
result = terminal("hermes kanban list")
# 解析状态并主动更新用户
for card in result:
    if card.done:     print(f"✅ {card.id} 完成")
    if card.running:  print(f"🔄 {card.id} 运行中")
    if card.blocked:  print(f"⛔ {card.id} 阻塞")

# 全部 done → 立即创建汇总卡（不等用户催）
print("三张卡全部完成，创建汇总...")
kanban_create(...)
```

### 用户问"卡死了吗"时的回复模式

当用户主动问进度时：
1. 立即检查 `hermes kanban list`
2. 如果全部 done → 立即创建汇总卡 + 告知用户
3. 如果有 running → 报进度 + 剩余时间
4. 如果有 failed → 说明原因 + 恢复方案
5. 长时间 todo → 检查 `hermes gateway status`

## Procedure

### 1. Draft and Read the Code

Read the file to review with `read_file`. Prepare the content to pass into Kanban card bodies.

### 2. Create 5 Worker Cards (Parallel, Include ALL Profiles)

**评审卡 body 必须包含断言声明段和验证命令段**（详见下文模板）。

**诚实硬条款（2026-08-29 用户要求，所有 agent 强制）**：禁止声称"已执行/已验证"——无命令输出=未验证，必须明确标注；无法验证的项标注「⚠️未验证」，不得冒充已通过；评审结论缺验证证据（命令输出/行号/数据点）→ 判定不合格，打回补验。

```python
# Must create ALL available worker profiles
t1 = kanban_create(
    title="【代码评审-架构】文件名",
    assignee="worker-glm",
    body=f"""请先加载检查清单：`skill_view(name='code-review-checklist')`

--- 断言声明 ---
• 架构假设: [你对该代码的主要架构假设，例如"模块A只被模块B调用"]
• 依赖假设: [例如"函数X只在Y条件下执行"]
• 类型假设: [例如"trade_cal.is_open 列类型为 int"]

--- 验证命令（至少执行 2 条，覆盖不同维度，在报告中注明输出）---
- [ ] ls <path> 确认文件存在（路径）
- [ ] PRAGMA table_info(xxx) 确认列类型（类型）
- [ ] stat -f %A <file> 确认权限（权限）
- [ ] SELECT typeof(col) FROM xxx LIMIT 1 确认类型（类型）
- [ ] SELECT col FROM xxx LIMIT 1 确认数量级（单位）

--- 评审正文 ---
评审以下代码的架构/可维护性/命名/模块边界：

```python
{code_content}
```
"""
)["task_id"]

t2 = kanban_create(
    title="【代码评审-逻辑】文件名",
    assignee="worker-kimi",
    body=f"""请先加载检查清单：`skill_view(name='code-review-checklist')`

--- 断言声明 ---
• 逻辑假设: [例如"循环内不产生副作用"]
• 边界假设: [例如"输入列表长度>0"]
• 类型假设: [例如"返回值类型为 float"]

--- 验证命令（至少执行 2 条，覆盖不同维度）---
- [ ] ls <path> 确认文件存在（路径）
- [ ] PRAGMA table_info(xxx) 确认列类型（类型）
- [ ] SELECT typeof(col) FROM xxx LIMIT 1（类型）

--- 评审正文 ---
评审以下代码的逻辑正确性/边界条件：

```python
{code_content}
```
"""
)["task_id"]

t3 = kanban_create(
    title="【代码评审-性能安全】文件名",
    assignee="worker-minimax",
    body=f"""请先加载检查清单：`skill_view(name='code-review-checklist')`

--- 断言声明 ---
• 安全假设: [例如"输入已过滤SQL注入"]
• 性能假设: [例如"该查询命中索引"]
• 资源假设: [例如"连接在使用后关闭"]

--- 验证命令（至少执行 2 条，覆盖不同维度）---
- [ ] ls <path> 确认文件存在（路径）
- [ ] stat -f %A <file> 确认权限（权限）
- [ ] PRAGMA table_info(xxx) 确认列类型（类型）

--- 评审正文 ---
评审以下代码的SQL性能/内存/安全风险：

```python
{code_content}
```
"""
)["task_id"]

# ⚠️ 必须包含xiaomi（用户反复强调）
t4 = kanban_create(
    title="【代码评审-数据完整性】文件名",
    assignee="worker-xiaomi",
    body=f"""请先加载检查清单：`skill_view(name='code-review-checklist')`

--- 断言声明 ---
• 数据假设: [例如"该字段单位是亿元"]
• 格式假设: [例如"trade_date 格式为 YYYYMMDD"]
• 一致性假设: [例如"表A和表B的code字段可关联"]

--- 验证命令（至少执行 2 条，覆盖不同维度）---
- [ ] SELECT typeof(col) FROM xxx LIMIT 1 确认类型（类型）
- [ ] SELECT col FROM xxx LIMIT 1 确认数量级（单位）
- [ ] PRAGMA table_info(xxx) 确认列类型（类型）

--- 评审正文 ---
评审以下代码的数据完整性/漏检/边界情况：

```python
{code_content}
```
"""
)["task_id"]
```

# ⚠️ 必须包含qwen（2026-08-22加入阵容，用户要求）
t5 = kanban_create(
    title="【代码评审-方案论证】文件名",
    assignee="worker-qwen",
    body=f"""请先加载检查清单：`skill_view(name='code-review-checklist')`

--- 断言声明 ---
• 方案假设: [例如"该设计满足当前需求且可扩展"]
• 论证假设: [例如"模块间依赖方向正确"]
• 一致性假设: [例如"方案与现有架构/数据流兼容"]

--- 验证命令（至少执行 2 条，覆盖不同维度）---
- [ ] ls <path> 确认文件存在（路径）
- [ ] PRAGMA table_info(xxx) 确认列类型（类型）
- [ ] SELECT typeof(col) FROM xxx LIMIT 1（类型）

--- 评审正文 ---
评审以下代码的整体方案论证：设计是否最优、跨维度整合是否有矛盾遗漏、是否有更优替代方案：

```python
{code_content}
```
"""
)["task_id"]
```

> ⚠️ **5个worker卡，一个不能少。** 忘记 `worker-xiaomi` 是用户多次纠正过的；`worker-qwen` 于 2026-08-22 加入阵容。

### Step 3: 等待完成后直接输出原始 5 份报告（停止假汇总）

> ⛔ **已停掉"无矛盾检测的汇总"步骤。** 当前策略：所有 worker 完成后，直接输出 5 份原始评审报告，不做汇总拼接。等阶段二（③ Orchestrator 断言对齐）上线后再恢复有意义的汇总。

```python
# Step 3a: 等待所有 worker 完成
cd ~/my_quant_system && python3 scripts/kanban_await.py t1 t2 t3 t4 t5 --timeout 600

# Step 3b: 读取 5 份原始报告
hermes kanban show t1
hermes kanban show t2
hermes kanban show t3
hermes kanban show t4
hermes kanban show t5
```

### 4. 自动推送结果（使用 kanban_await.py） ⭐ 默认路径

创建卡后**必须**启动自动推送脚本，替代手动轮询。这是默认行为，不是可选项：

```bash
# 注意：kanban_await.py 只支持 --timeout 和 --interval，不支持 --extra-ticks 或 --background
# 推荐做法：打开 terminal(background=true, notify_on_complete=true) 运行
cd ~/my_quant_system && python3 scripts/kanban_await.py t1 t2 t3 t4 t5 --timeout 600
```

**验证状态**: ✅ 已在 2026-07-11 的2轮评审中实测通过（GLM+Kimi+MiniMax 3张卡，458秒自动推送完成）

**原理**: `kanban_await.py` 使用 `hermes kanban show --json`（结构化API，非文本正则），每15秒轮询，卡完成时自动打印摘要到终端。支持 `--timeout`（默认600s）和 `--interval`（默认15s）。**注意：不含 --extra-ticks 参数**，超时后直接以 exit code 1 退出，请配合 `hermes kanban show <id>` 手动检查超时卡。

**超时兜底**: kanban_await.py 超时退出后，应立即用 `hermes kanban show <id>` 检查各卡状态。如果有已完成但仍未被读取的卡，手动读取结果。

**注意**: 如果 `kanban_await.py` 不可用（新环境/路径不存在），退回到 Step 4b 手动轮询。

### 4b. 传统模式：无自动推送时的手动轮询

如果 `kanban_await.py` 不可用，必须主动用 `hermes kanban list` 每30-60秒检查一次。
**不能等用户问进度。**

### 5. Read and Classify Results

```bash
hermes kanban show <synthesis_task_id>
```

Classify issues:
| Level | Meaning | Action |
|-------|---------|--------|
| 🔴 P0 | Blocking bug, data corruption, security hole | Must fix before proceeding |
| 🟡 P1 | Inefficiency, code smell, edge case missed | Fix unless high effort |
| 🟢 P2 | Style preference, future optimization | Log, don't block |

### 6. Fix and Re-verify

Fix all 🔴 issues. **修复用 delegate_task，不重新派 Kanban 修复卡。**
Kanban worker 只有 CLI 工具集，适合评审但不适合执行修复。`delegate_task` 的子 agent 可以跑脚本、查库、改文件：

```python
delegate_task(
    tasks=[
        dict(goal="修复P0-1: ...", context="具体问题描述 + 文件路径 + 数据库路径"),
        dict(goal="修复P0-2: ...", context="..."),
    ]
)
```

修复验证通过后，跑一次再评审（同 Step 1-5）。

### 7. Archive Completed Cards

```bash
hermes kanban archive <task_id>    # Clean up
```

## Worker Failure Handling

Workers can crash or timeout at runtime. The system handles this in layers:

1. **Auto retry** — dispatcher retries up to `failure_limit` (default 2, meaning one retry)
2. **If retries exhausted (no-parents模式)** — orchestrator 自己通过 `kanban show` 读取各卡状态，对 failed 的卡跳过，继续合成已有结果。**不会死锁。**
3. **Legacy: If retries exhausted and card has parents** — the synthesis card stays `todo` forever (parents deadlock). Mitigations:
   - `kanban_reclaim <task_id>` to reset the failed card and retry
   - Create a new synthesis card *without* parents that only references the completed worker results

## Pitfalls

- **kanban_await.py timeout near-miss**: 当运行缓慢的 worker（如 xiaomi 耗时 545s）接近 600s 超时时，可能恰好在上次轮询后、超时检查前完成。kanban_await.py **不含 --extra-ticks 参数**（该参数不存在），超时后直接 exit code 1 退出。**兜底措施**：超时后立即用 `hermes kanban show <id>` 手动检查各卡状态——部分卡可能已在超时边缘完成。如果有多张卡同时等，先检查所有卡再决定是否重跑。对于预估超时的场景，直接使用 `--timeout 900`。 |
- **parents deadlock (已在新流程中规避)**: 如果仍使用 `parents=[...]` 且 worker 失败，synthesis 卡永久死锁。解决办法：创建不带 parents 的 fallback 卡，或手动 `kanban show` 读结果。
- **Orchestrator 自崩溃**: orchestrator 被派发后它的模型调用可能失败。此时 worker 已完成但无人合成。恢复：`kanban show t1/t2/t3` 手动读取各 worker 结果自行总结。
- **Gateway 故障**: 创建卡后长时间（>2分钟）所有卡状态为 `todo`，先运行 `hermes gateway status` 检查 gateway 是否存活。如果挂了，`hermes gateway run --replace` 重启。
- **时序竞态**: 无 parents 模式后，orchestrator 被立即派发。如果此时 worker 还没完成，orchestrator 读到的是 todo。**必须在 orchestrator body 中写明轮询逻辑**：`读取t1/t2/t3，如有任一为todo/blocked，等120秒后重读，最长等5分钟。超过的标记为[worker不可用]。`
- **Kimi 连续失败**: Kimi K2.6 已知不稳定（~2/9 crash率）。重试2次后仍失败：建议切换为其他 worker 代审逻辑维度，或用 terminal 直调 Kimi API 做补充。
- **Kimi 卡在 running 状态（不 crash 也不完成）**: 与 crash 不同，Kimi 可能显示 "running" 长达 10+ 分钟而无任何输出。这比 crash 更难检测——因为系统不会自动重试（未到 failure_limit）。**处理方式**：如果已有 ≥4/5 的 worker done 且 Kimi 超预期时间仍 running，直接跳过它，用其余 4 家结论汇总。不等了。
- **多 worker 同时失败**: 如果 3 个 worker 中 ≥2 个失败，orchestrator 只有 1 份结果，合成质量严重下降。建议告知用户后重试整个周期。
- **Worker-glm "needs_input" blocking**: worker-glm 完成时可能状态为 `blocked(needs_input)` 而非 `done`。修复：`kanban complete <task_id> --summary "Reviewed, accepted"`
- **no auto-notify**: `kanban_complete` 的摘要不会自动推送到默认 profile 的会话。必须手动 `kanban_show`。
- **归档即清理**: worker 的工作区文件在归档后被清理。`kanban_show` 读到结果后记得保存，再 `kanban archive`。

## Verification

```bash
# Create a quick 2-card test
t1=$(hermes kanban create "【测试】验证GLM可达" --assignee worker-glm --body "只回复OK")
sleep 90 && hermes kanban show $(echo "$t1" | grep -o 't_[a-f0-9]*')
```

## Support Files

- `references/kanban-timing-benchmarks.md` — 实测等待时间基准（15s dispatch），用于制定通信节奏
- `references/kanban-await-tool.md` — kanban_await.py 自动推送工具的用法和JSON格式说明
- `scripts/kanban_await.py` — 自动轮询脚本入口，skill目录内的副本
