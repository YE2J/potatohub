---
name: review-driven-execution
description: "Full-stack review-driven execution workflow: every step goes through 3-agent parallel review → auto-fix → execute → review → auto-fix → next step. Multi-phase project structure."
version: 1.0.0
author: User-defined workflow
license: MIT
metadata:
  hermes:
    tags: [workflow, review, multi-agent, quality, auto-fix, phase-management]
    related_skills: [plan, requesting-code-review, subagent-driven-development, minimax-auditor]
---

# Review-Driven Execution Workflow

**Core principle:** Every step of every phase goes through 3-agent review BEFORE and AFTER execution, with auto-fix between each review. No step is too small to review.

This is the DEFAULT workflow for this user. Only deviate when the user explicitly says "skip review" or "直接做" for a specific step.

## When to Use

- Any multi-step execution task (coding, data analysis, research, config changes)
- Multi-phase projects (Phase 1 → Phase 5)
- The user says "每做一步都要三个agent评审"
- A-share factor analysis, case collection, or any systematic investigation
- Code generation that affects production or data pipelines

**Do NOT skip for:** "simple" steps, "obvious" changes, or when you feel confident. The user has explicitly stated this applies to ALL steps.

## Phase Structure

For multi-phase projects, define phases upfront:

```yaml
Phases:
  - Phase 1: [name, goal, steps, target output]
  - Phase 2: [name, goal, steps, target output]
  ...
  - Phase N: [name, goal, steps, final deliverable]
```

Each phase has an **entry criterion** (prerequisites done) and an **exit criterion** (phase deliverable verified).

## Per-Step Execution Loop

```
┌──────────────────────────────────────────┐
│  DEFINE: What does this step accomplish  │
│  (1-2 sentence goal + expected output)   │
└──────────────────┬───────────────────────┘
                   ▼
┌──────────────────────────────────────────┐
│  PRE-REVIEW: 3 parallel agents           │
│  • Agent A: data completeness / logic    │
│  • Agent B: feasibility / execution      │
│  • Agent C: quality / consistency        │
└──────────────────┬───────────────────────┘
                   ▼
┌──────────────────────────────────────────┐
│  CONSOLIDATE review feedback             │
│  Classify into:                          │
│  🔴 Blocking (must fix)                  │
│  🟡 Non-blocking (fix if easy)           │
│  💡 Suggestions (note for future)        │
└──────────────────┬───────────────────────┘
                   ▼
┌──────────────────────────────────────────┐
│  REPORT findings to user FIRST           │
│  • Summarize what was found before       │
│    touching any code                     │
│  • Ask user: "修？继续？"                │
│  • Never silently start fixing           │
└──────────────────┬───────────────────────┘
                   ▼
┌──────────────────────────────────────────┐
│  AUTO-FIX all blocking issues            │
│  • If fix introduces new issues →        │
│    re-run pre-review on changed parts   │
│  • Max 3 fix cycles before escalate      │
└──────────────────┬───────────────────────┘
                   ▼
┌──────────────────────────────────────────┐
│  EXECUTE the step                        │
│  (use tools: terminal, write_file, API)  │
└──────────────────┬───────────────────────┘
                   ▼
┌──────────────────────────────────────────┐
│  POST-REVIEW: 3 parallel agents          │
│  • Quality check of output               │
│  • Bug/error detection                   │
│  • Consistency with overall goal         │
└──────────────────┬───────────────────────┘
                   ▼
┌──────────────────────────────────────────┐
│  AUTO-FIX post-execution issues          │
│  • If review agents find bugs, apply     │
│    fixes INLINE (not re-dispatch)        │
│    — tool calls within review are faster │
│  Re-execute if needed                    │
└──────────────────┬───────────────────────┘
                   ▼
┌──────────────────────────────────────────┐
│  🔍 AUDITOR (optional 4th agent)         │
│  Cross-check all 3 review reports        │
│  • Contradictions between agents         │
│  • Missed global-level issues            │
│  • Cross-file consistency                │
│  Load skill_view('minimax-auditor')      │
└──────────────────┬───────────────────────┘
                   ▼
┌──────────────────────────────────────────┐
│  VERIFICATION REVIEW (if fixes applied)  │
│  Dispatch 4 agents with perspectives:    │
│  A: Fix correctness ─ are fixes right?   │
│  B: Regression ─ did fixes break things? │
│  C: Completeness ─ what was missed?      │
│  D: Integration ─ do parts still work?   │
│  → Auto-fix any P0 found, then proceed   │
└──────────────────┬───────────────────────┘
                   ▼
┌──────────────────────────────────────────┐
│  REPORT final result to user             │
│  • Consolidated summary of what was done │
│  • Any remaining unfixed items + why     │
│  • Ask if they want to proceed or fix    │
│    remaining items                       │
└──────────────────────────────────────────┘
```

## 代码质量评审 — 4-Agent Kanban 派发（强制）

**规则：** 每次起草代码初稿后（包括但不限于：调试、脚本、后端、前端、数据库、API、SQL查询、配置修改），都必须安排 4 个 Agent 评审代码质量、进行效率优化和排查 bug，**通过后方可执行或交付**。

触发场景举例：
- 写了一个 Python/JS/TS/Shell 脚本 → 评审
- 修改了数据库 SQL/表结构 → 评审
- 写了前端页面/组件 → 评审
- 调试定位到 bug 后写了修复代码 → 评审
- 后端 API 路由/中间件/模型 → 评审
- 重构/优化现有代码 → 评审

### ⚠️ 关键设计决策：汇总卡永远不要用 parents

**核心规则：orchestrator 汇总卡不能带 `parents=[t1,t2,t3]`。** 任何 worker 崩溃都会导致 orchestrator 永久死锁，进度完全停止。

**正确做法：**
1. 先创建 3 张 worker 卡
2. 定期 `hermes kanban list` 检查，等全部 worker 完成（done）后再创建汇总卡
3. 汇总卡不带 `parents` 参数
4. 在 orchestrator body 中写 `kanban show` 指令让它自己读取 worker 结果

**失败处理：** 如果 3 个 Worker 中有任一失败（status=failed），由于不设 parents 依赖，orchestrator 不会死锁。orchestrator 会跳过 failed 卡，继续合成已有结果，标记【失败：该worker不可用】。

### 修复→再评审循环「双工具」分工

Kanban 评审发现 🔴 问题后，**不要用 Kanban 去修**。使用 `delegate_task` 派发 fix agent 去执行修复：

```
Kanban 4模型评审 (发现 🔴/🟡/🟢)
  ↓
delegate_task 派发fix agent
  ├─ 子agent有完整Python/shell工具集（查库、改文件、跑脚本）
  └─ 无parents死锁风险，独立运行
  ↓ 修复完成
Kanban 4模型再评审 (验证修复质量 + 排查新bug)
  ↓
修改建议清单 → 闭环
```

### 自动推送（kanban_await.py）

Kanban 卡完成后**不会自动通知当前对话**。必须主动推。

**标准做法**：创建所有 worker 卡后立即启动 `kanban_await.py`：

```bash
python ~/my_quant_system/scripts/kanban_await.py t_glm t_kimi t_auditor --timeout 900 &
```

`kanban_await.py` 使用 `hermes kanban show --json`（结构化API），每15秒轮询，卡完成时自动打印摘要到终端。

**参考耗时**（15s dispatch interval）：
| Worker | 模型 | 典型耗时 |
|--------|------|:--------:|
| `worker-glm` | GLM-5.2 | ~3-5min |
| `worker-kimi` | Kimi K2.7-code | ~6-10min（已知不稳定）|
| `worker-auditor` | MiniMax M2.7 | ~5-8min |
| `orchestrator` | DeepSeek V4 Flash | ~30-60s |

`--timeout` 建议设为 900s（15分钟），覆盖最慢情况。

**不需要用户问进度**：不要等用户说"卡死了吗"再检查。创建卡时告知预计时间，然后主动用 `kanban list` 或 `kanban_await.py` 监控。

### 实测验证时间（2026-07-09~07-11，P1→P4 完整搭建，3轮迭代）：\n1️⃣ Kanban评审发现7个P0 → delegate_task修复 → Kanban再评审发现3个新P0\n2️⃣ delegate_task再修 → Kanban三评审\n3️⃣ 闭环，通过\n4️⃣ P2~P4 各引擎编码后立即4-agent评审→修P0→通过，形成「编码→评审→修→通过」的固定循环\n\n**注意**：用户明确表达了「做完一件任务就评审任务质量和排查bug」的偏好，这是**默认行为**，不是可选流程。

**为什么用 delegate_task 修：**
- delegate_task 的子 agent 在后台独立运行，无 parents 死锁风险
- delegate_task 支持混合模式（跑脚本+查数据+修复）
- Kanban 的 worker 只有 CLI 工具集，不适合做复杂修复

### 完整工作流

```
起草方案/代码初稿
  ↓
STEP 1: 创建 3 张 Kanban 卡（Worker 评审，不带 parents）
  ├─ kanban_create("【评审-架构】...", assignee=worker-glm)
  ├─ kanban_create("【评审-逻辑】...", assignee=worker-kimi)
  └─ kanban_create("【评审-性能安全】...", assignee=worker-auditor)
  ↓\nSTEP 2: 启动自动推送 + 等全部 3 个 worker 完成（done）\n  ├─ hermes kanban list （15s 派发间隔，约2-8分钟）\n  ├─ **自动推送**: `python ~/my_quant_system/scripts/kanban_await.py t_glm t_kimi t_auditor &`\n  └─ 注意 Kimi 较慢（~6-10min），MiniMax ~5-8min
  ↓
STEP 3: 创建汇总卡（不带 parents！body 写 kanban show 指令）
  ├─ kanban_create("【合成】...", assignee=orchestrator)
  └─ 读 kanban show 等待 orchestrator 完成
  ↓
STEP 4: 分类 🔴/🟡/🟢，汇报给用户
  ↓
STEP 5: 如果有 🔴 P0 → delegate_task 派发 fix agent
  ├─ delegate_task(tasks=[{goal, context}])
  └─ wait for result
  ↓
STEP 6: Kanban 再评审（debug verify，同 STEP 1-4）
  ↓
STEP 7: 闭环，推进下一步
```

### 评审视角（4 个 Agent，3 个 Worker + orchestrator 汇总）

| 角色 | Profile | 模型 | 评审维度 | 关注点 |
|------|---------|------|---------|--------|
| 🏗 **架构/可维护性** | `worker-glm` | GLM-5.2 | 代码结构、复用性、命名、模块边界、文件大小 | 重复代码、函数过长、import 规范 |
| 🔬 **逻辑/正确性** | `worker-kimi` | Kimi K2.7-code | 逻辑正确性、边界条件、测试覆盖 | off-by-one、空值处理、数据类型兼容 |
| ⚡ **性能/安全** | `worker-auditor` | MiniMax M2.7 | SQL 性能、内存使用、安全风险、异常处理 | N+1查询、索引失效、静默吞异常 |
| 👤 **汇总** | `orchestrator` | DeepSeek Flash | 整合 3 份评审，分类修复优先级 | 矛盾点仲裁、遗漏补充 |

### Kanban 派发代码（正确的无 parents 模式）

```python
# STEP 1: 创建 3 张 worker 卡
t1 = kanban_create(
    title=f"【代码评审-架构】{文件名}",
    assignee="worker-glm",
    body=f"评审以下代码的架构/可维护性/命名/模块边界：\n\n```python\n{code_content}\n```"
)["task_id"]

t2 = kanban_create(
    title=f"【代码评审-逻辑】{文件名}",
    assignee="worker-kimi",
    body=f"评审以下代码的逻辑正确性/边界条件：\n\n```python\n{code_content}\n```"
)["task_id"]

t3 = kanban_create(
    title=f"【代码评审-性能安全】{文件名}",
    assignee="worker-auditor",
    body=f"评审以下代码的SQL性能/内存/安全风险：\n\n```python\n{code_content}\n```"
)["task_id"]

# STEP 2: 等待全部 worker done（用 hermes kanban list 检查）
# 可在此处通知用户等待

# STEP 3: 等全部 done 后再创建汇总卡（不带 parents！）
kanban_create(
    title="【合成】代码评审汇总",
    assignee="orchestrator",
    body=f"""请汇总以下3张卡的评审结果：
- {t1} (worker-glm: 架构评审)
- {t2} (worker-kimi: 逻辑评审)
- {t3} (worker-auditor: 性能安全评审)

请用 `hermes kanban show {t1}` / `{t2}` / `{t3}` 分别读取每张卡的结果。
对已经 done 的卡做汇总，对 failed/crashed 的卡标记【失败：该worker不可用】。
最终输出分类(🔴/🟡/🟢)和矛盾仲裁。"""
)
```

### 评审结果分类

| 等级 | 含义 | 处理 |
|------|------|------|
| 🔴 P0 阻塞 | 功能错误、数据损坏、安全漏洞 | 必须修复后才能执行 |
| 🟡 P1 重要 | 效率低下、代码异味、边界遗漏 | 修复，除非改动很大 |
| 🟢 P2 建议 | 风格/命名偏好、未来优化 | 记录，不阻塞交付 |

### 例外情况
- 用户明确说"直接做"或"skip review" → 跳过
- 代码改动只有 1-3 行且纯机械性（改个变量名、调个常量值）→ 可跳过
- 不确定是否符合例外条件 → 按默认执行评审

| Agent | Perspective | Key Questions | Real findings from ic_diagnosis.py review (2026-07) |
|-------|-------------|---------------|------------------------------------------------------|
| 1 | **Code Architecture** | Module design, duplication vs reuse (check existing modules first!), naming conventions (PEP8), file size (target <800 lines), HTML/CSS not hardcoded in Python strings, function boundaries, imports | 🔴 `_load_stock_map()` 3-file duplication (ic_diagnosis.py + ic_analyzer.py + factors.py); SIGNAL_DEFS 4 conditions repeated 7-8× via lambda; 1119-line file too long |
| 2 | **Data Logic** | Signal/criteria match config.py exactly, forward return calculations correct (`shift(-n)/s-1`), exclude vs delete semantics, binary signal IC validity, date format handling (`mixed`), InnerCode↔SecuCode mapping | 🔴 暗盘inflow缺"连续2日"约束 vs backtest_v4.py (IC结果偏误); 自选股硬编码set与config.py dict不同步 |
| 3 | **SQL/Performance** | Connection reuse, full-load memory estimate (<2GB), try-except specificity, index coverage, date-format issues in SQL WHERE | 🔴 LIKE '%000300%'前导通配符使索引失效; kline全表267万行拉到Python再过滤; df.copy() 192次深拷贝285万行DataFrame |
| 4 | **Error Handling** | Silent exception swallowing, NaN/Inf propagation risk, empty-data crash chain, missing-file fallbacks, long-running job progress feedback, path-not-found failures, ZeroDivision risks | 🔴 except Exception静默吞错误掩盖schema变更; 主流程无异常隔离(一个崩全部停); HTML自定义输出路径无mkdir; 全市场运行30分钟无进度条 |

### Script Pre-Review Self-Checklist

Before dispatching 4-agent review, verify:

- [ ] Signal definitions match `config.py V4_PARAMS` exactly (backtest_v4.py is reference)
- [ ] Script does NOT call `factor_pipeline.py`'s stub/TODO methods — those are abandoned stubs; actual computation is in `strategy_library.indicators.*` (calc_gs_signal, calc_zhuli_radar, calc_ai_activity, calc_dark_pool, calc_zhuli_holdings). The real CLI entry point is `import_daily_factors.py`.
- [ ] Date format: `daily_factors.trade_date` is `YYYY-MM-DD` (~97.6%), `daily_kline.date` is mixed — optimization: try `%Y-%m-%d` first, fall back to `%Y%m%d` for parse failures
- [ ] stock_code: InnerCode (numeric like `398589`) vs SecuCode (6-digit like `000988`) — mapping via `all_ashare_stocks.csv`
- [ ] Forward return: `shift(-n) / s - 1` returns NaN at data tail — downstream handles it
- [ ] Memory: 5000 stocks × 500 days × 50 cols × 8 bytes ≈ 1GB — fits in 16GB
- [ ] Console progress: print for every section that runs >30s
- [ ] CLI: argparse with `--db`, `--start`, `--end`, `--output`
- [ ] Chart.js fallback: if vendor file missing, HTML works without charts
- [ ] Duplicate code: check `ic_analyzer.py` for existing `_load_stock_map()`, `load_data()`, `compute_ic()` before re-implementing

## Multi-Agent Review Perspectives

Select 3 perspectives appropriate for the task type:

### For Data/Research Tasks (e.g., A-share case analysis)
| Agent | Perspective | Questions to ask |
|-------|-------------|-----------------|
| A | **Data completeness** | Are all relevant data sources covered? Any missing dimensions? |
| B | **Logic/reasoning** | Are conclusions/data-supported? Any logical gaps? |
| C | **Feasibility/execution** | Can this be executed with available tools? Within sandbox limits? |

### For Code/System Tasks
| Agent | Perspective | Questions to ask |
|-------|-------------|-----------------|
| A | **SRE/reliability** | Failure modes, race conditions, edge cases? |
| B | **Architecture/design** | Coupling, complexity, extensibility? |
| C | **Implementation/feasibility** | Environment constraints, command availability? |

### TDX/同花顺 Formula Review Checkpoints

When reviewing a 同花顺/通达信 (TDX) formula (e.g., from `ths-formula-authoring`):
| Agent | Perspective | Specific checks |
|-------|-------------|----------------|
| A | **Syntax** | Color names valid (no COLORLIGRAY), variable names no `()`/`%`/`-`, DRAWICON types correct (4=buy ↑, 5=sell ↓), DRAWBAND compatible |
| B | **Logic** | KDJ/RSI/MACD calculations match Python backtest exactly; buy/sell threshold semanics (CROSS vs bare comparison) correct; signal frequency reasonable |
| C | **Practicality** | Signal can be acted on next day (no limit_up/limit_down on signal day), visual clarity (not too many overlapping elements), stop-loss is execution rule not formula logic |

**Known TDX pitfalls to check for:**
- `COLORLIGRAY` is NOT a valid color → use `RGB(160,160,160)` 
- Variables with `()` or `%` in names may fail on old versions → use `_pct` suffix
- DRAWBAND not supported in very old versions (pre-2018); STICKLINE fallback if needed
- TDX has no position-level memory; stop-loss and position sizing are execution rules, not formula-encodable
- `SMA(X,3,1)` is NOT the same as `MA(X,3)` — SMA with M=1 is the KDJ standard; MA is simple average

## Optional: 4th Agent — Architecture/Consistency (for Ecosystem Reviews)

When reviewing **interdependent script ecosystems** (e.g., multiple cron pipelines writing to the same DB, a morning report reading from several pipeline tables), replace the Auditor with an **Architecture & Consistency** agent that focuses on cross-cutting concerns the 3 code-level reviewers will miss.

### When to use Architecture agent vs Auditor

| Scenario | Use |
|----------|-----|
| Single script / isolated task | Auditor (review 3 agent reports for contradictions) |
| ≥3 interdependent scripts + shared DB | **Architecture** (dispatch AFTER code-level reviews complete, so it can reference their findings) |

### Architecture Agent dimensions

| Dimension | What to check | Real findings from 2026-07-09 pipeline review |
|-----------|---------------|----------------------------------------------|
| **Cross-script field naming** | DB column names vs what each script writes | `buy_elg_amount` written to `elg_net_amt` column — buy amount stored as net amount |
| **Date format consistency** | Do all scripts use the same format? | `daily_kline`: 18K rows `YYYYMMDD` + 2.6M `YYYY-MM-DD` → `MAX(date)` returns wrong row |
| **PK design** | Does PK support multi-source? | `moneyflow_daily` PK lacks `data_source` → second pipeline overwrites provenance |
| **Cron wrapper hygiene** | Are all cron scripts using the same logging framework? | 5 Financial-API crons had no `cron_log_helper` integration |
| **Error handling coverage** | Is every failure path handled? | `cron_log_helper` macOS `date +%s%3N` crash → 42 zombie records |
| **Dead/orphaned code** | Scripts that exist but are no longer referenced | 3 deprecated scripts not cleaned up |

### Deployment pattern

```
Phase 1: Dispatch A/B/C in parallel (code-level review)
    ↓ (wait for all 3 to complete)
Phase 2: Dispatch Agent D (architecture) with reference to A/B/C findings
    ↓
Phase 3: Consolidate all findings, fix P0s, re-review if needed
```

## Delegation Pattern for Reviews

Dispatch all 3 agents in parallel using `delegate_task` with the `tasks` array:

```python
delegate_task(
    tasks=[
        dict(goal="Agent A goal", context="Shared context..."),
        dict(goal="Agent B goal", context="Shared context..."),
        dict(goal="Agent C goal", context="Shared context..."),
    ]
)
```

**Key:** Put the FULL context in each task's context field — subagents have NO memory of the conversation.

For complex tasks, optionally add a 4th agent (Auditor) after the 3-agent review cycle completes. See the **Optional: 4th Agent — Auditor** section above for when and how.

## Auto-Fix Rules

- Fix ALL 🔴 blocking issues before executing the step
- Fix 🟡 non-blocking only if it takes <30 seconds and doesn't risk introducing new issues
- Max 3 fix cycles before escalating to the user
- After each fix, verify with a re-review of the changed parts only
- Never ship a step with known unsolved blocking issues to the next step
- **Inline fix pattern**: When review agents discover bugs in their own review, apply the fix directly in the review agent's turn (via `patch`/`write_file` in the agent's session) rather than re-dispatching a separate fix agent. This is faster and avoids context fragmentation. The parent should then verify the fix was applied.

### Post-Review Finding Severity Classification

When consolidating 3-agent review output, classify findings by severity:

| Severity | Label | Meaning | Action |
|----------|-------|---------|--------|
| **P0 🔴** | Blocking | Data corruption, wrong conclusions, code crashes | Must fix before proceeding |
| **P1 🟡** | Important | Missing functionality, UI/text errors, suboptimal results | Fix if <30s; document otherwise |
| **P2 🟢** | Nice-to-have | Methodological nuances, edge cases, cosmetic issues | Document as future work; do not delay execution |
| **💡** | Suggestion | Alternative approaches, future extensions | Log for later; do not implement now

**Real session example** (AI case factor analysis, 2026-07-06):
- P0: RSI NaN bug → consecutive up days produce RSI=NaN (fixed)
- P0: moneyflow data gap → all fund flow factors null (documented)
- P1: HTML text "4 days lead" should be "10.5 days" (fixed)
- P2: ICIR uses time-series IC, not standard cross-sectional (documented as note)

**Real session example** (data pipeline ecosystem review, 2026-07-09):
- P0: `get_latest_trade_date()` used stale local `trade_cal` table → skipped 4 trading days
- P0: Field mapping: `buy_elg_amount` written to `elg_net_amt` column (buy amount != net amount)
- P0: `cron_log_helper` macOS `date +%s%3N` crash → 42 zombie records, all cron jobs exit 1
- P1: `daily_kline` mixed date formats (18K YYYYMMDD + 2.6M YYYY-MM-DD) → MAX(date) returns wrong row
- P1: 5 Financial-API cron wrappers missing `cron_log_helper` integration
- P2: deprecated scripts not cleaned up

### Common pitfalls to proactively check in pipeline reviews

| Pitfall | Signal | Fix |
|---------|--------|-----|
| `get_latest_trade_date()` queries local cache first | Pipeline skips new data days silently | Always call API directly; cached table goes stale |
| Field named `buy_*` written to `*_net_amt` column | Wrong sign/scale | Verify API returns net (buy-sell) or gross (buy-only) before mapping |
| `COUNT(DISTINCT pk_col)` on PK-covered column | Extra B-tree sort | Use `COUNT(*)` instead (cheaper on indexed cols) |
| Mixed date formats in TEXT PK | `ORDER BY date DESC` returns wrong row | Converge on `YYYY-MM-DD`; use `REPLACE(date,'-','')` in sort |
| `except Exception: pass` hides errors | Feature appears empty with no explanation | Log the error; let user see what failed |
| macOS cron helper uses `date +%s%3N` | All crons exit 1 despite success | Use `python3 -c "import time; print(int(time.time()*1000))"` |

## Escalation

If a step's review produces 🔴 blocking issues that cannot be auto-fixed:
1. Summarize the issue(s) clearly
2. Present options for the user to decide
3. Implement the chosen option
4. Re-run the review loop on the fix

## Pitfalls

- **Kanban silent completion (two flavors)** — Kanban cards don't auto-notify. Two failure modes observed:
  1. *Silent completion*: cards finish but nobody reports it → user asks "卡死了吗?". Fix: use `kanban_await.py` auto-push or poll every 30-60s.
  2. *Silent synthesis*: workers all done but orchestrator not created → user asks "为什么还没汇总". Fix: check `kanban list` once workers' expected time elapses; create orchestrator immediately. Never wait to be asked.
- **Subagents have no memory** — always pass complete context in the `context` field
- **Language mismatch** — if the user communicates in Chinese, tell subagents in context to respond in Chinese
- **Too many fix cycles** — if fixing one issue creates another after 3 cycles, escalate
- **Review fatigue** — keep each review focused (3 agents, 1-2 questions each); avoid 10-agent reviews
- **Skipping for "obvious" steps** — don't. The user told you to review every step.
- **🚨 After review results arrive: report before acting.** This is a HARD RULE, not just a suggestion. When a subagent returns findings (async `delegate_task` batch complete message), your FIRST response must be a summary to the user with the key findings, severity classification, and a question asking what to do next. Do NOT start reading full reports, fixing code, or analyzing in silence. The user needs to see what was found before you touch code. Pattern: summarize → ask "修？继续？" → only fix after user response. Violating this rule looks like the system is hung and erodes user trust.

## Support Files

This skill includes:
- `references/ic-diagnosis-methodology.md` — 5-axis framework for diagnosing negative IC signals. Refer to this when building or reviewing factor analysis scripts.
- `references/noagent-report-script-checklist.md` — 3-agent review checklist for no_agent cron report scripts. Use when reviewing scripts that query SQLite + cron output files and produce formatted output.
- `references/three-layer-decision-framework.md` — A-share three-layer system overview (L1 temperature → L2 sector rotation → L3 valuation). Contains the complete data pipeline timetable (18:00~20:00) and engine file listing.
