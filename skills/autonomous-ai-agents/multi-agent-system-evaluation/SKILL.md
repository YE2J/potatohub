---
name: multi-agent-system-evaluation
description: "Parallel multi-agent evaluation of system/strategy proposals using 4 specialized roles (Architect, Analyst, PM, Risk/Ops). Covers task decomposition, parallel dispatch via Kanban or delegate_task, role-specific evaluation checklists, disagreement resolution, and synthesis into structured roadmaps with verified execution."
version: 1.3.0
tags: [multi-agent, evaluation, architecture, quant, system-design]
---

# Multi-Agent System Evaluation

## When To Use

Use this skill for any **non-trivial system/strategy design proposal** where:
- You need to evaluate feasibility from multiple perspectives
- The proposal has technical + domain + product + operational dimensions
- A single agent's view would miss important risks
- The user wants a thorough analysis before committing to implementation

Do NOT use for:
- Simple yes/no questions (just answer directly)
- Single-dimension technical questions (use the relevant domain skill)
- Tasks where the user explicitly wants a quick answer

## Core Methodology: 4-Role Parallel Evaluation

Dispatch **4 sub-agents in parallel** (max 3 per batch due to concurrent_children limit, send 4th separately):

| Role | Perspective | Evaluates |
|------|-------------|-----------|
| 🔧 **System Architect** | Technical feasibility, data pipelines, performance, DB, scalability | DB limits, cron reliability, factor pipelines, Mac Mini resource constraints, SQLite bottlenecks, incremental computation design, power consumption |
| 📊 **Financial Analyst / Strategy Researcher** | Investment logic, factor validity, market microstructure | Whether the user's investment philosophy actually holds in A-shares, IC diagnostics, factor crowding, market state dependency, academic references, risk warnings |
| 🎯 **Product Manager** | User needs, MVP definition, iteration roadmap, priority | What the user actually needs vs what they asked for, Phase 1/2/3 roadmap, success metrics, priority matrix (Impact × Urgency × Effort), things NOT to build |
| ⚠️ **Risk / Ops Specialist** | Data safety, cron reliability, backup, error propagation | Backup status, cron failure modes, DB corruption risk, checksum coverage, silent failures, recovery procedures, Mac Mini uptime and cooling |

## Task Decomposition Pattern

### Context each agent needs (ALL must be provided):
```
- The user's core philosophy / goal
- Complete system inventory (tables, factors, cron, skills, DB size)
- The proposed architecture / change
- Hardware constraints (Mac Mini M4 16GB is the baseline)
- Their specific role's evaluation lens
```

### Dispatch Pattern — Kanban (recommended for multi-model)

For true **multi-model dispatch** where each role runs on a different LLM (e.g. Kimi for research, GLM for code, MiniMax for audit), use Kanban cards instead of delegate_task. `delegate_task` has a known bug where all children inherit the parent model regardless of delegation config.

**⚠ CRITICAL: Do NOT use `--parent` / `parents=[]` for the synthesis card.**
Any worker crash → synthesis card deadlocks forever (see Pitfalls → "Kanban parents 死锁风险").
Use the parent-free pattern below: wait for all workers to reach `done`, THEN create the synthesis card with `kanban show` instructions.

**CLI syntax (preferred — works from any Hermes terminal):**
```bash
# 1. Create 3 worker cards (parallel execution) — no --parent
T1=$(hermes kanban create "【评估:架构师】标题" --assignee worker-kimi --body "任务描述")
T2=$(hermes kanban create "【评估:分析师】标题" --assignee worker-glm --body "任务描述")
T3=$(hermes kanban create "【评估:审计师】标题" --assignee worker-minimax --body "任务描述")

# 2. Wait for all workers to complete (check every 60s)
hermes kanban list   # wait until all 3 show status=done

# 3. Create synthesis card — NO --parent flag
hermes kanban create "【合成】多Agent评估汇总" --assignee orchestrator \
  --body "请汇总以下评审结果：
1) $T1 (worker-kimi: 研究员)
2) $T2 (worker-glm: 工匠)
3) $T3 (worker-minimax: 审计师)

用 kanban show 读取各卡。对 done 卡汇总，对 failed/crashed 标记【不可用】。
输出分类(🔴/🟡/🟢)和矛盾仲裁。"

# 4. Read completed synthesis
hermes kanban show <synthesis_task_id>

# 5. If worker-glm is "blocked" (needs_input), force-complete it:
hermes kanban complete <T2> --summary "Accepted"
```

**Python SDK syntax (alternative — requires Hermes Python venv):**

```python
# 1. Create independent work cards (parallel execution) — no parents
t1 = kanban_create(
    title="【评估:架构师】...",
    assignee="worker-kimi",
    body="role and task description"
)["task_id"]

t2 = kanban_create(
    title="【评估:分析师】...",
    assignee="worker-glm",
    body="role and task description"
)["task_id"]

t3 = kanban_create(
    title="【评估:审计师】...",
    assignee="worker-minimax",
    body="role and task description"
)["task_id"]

# 2. Periodically check kanban list until all 3 are done
# 3. Create synthesis card WITHOUT parents
kanban_create(
    title="【合成】多Agent评估汇总",
    assignee="orchestrator",
    body=f"""请汇总以下3张卡的评审结果：
- {t1} (worker-kimi: 研究员)
- {t2} (worker-glm: 工匠)
- {t3} (worker-minimax: 审计师)
用 kanban show 分别读取。对 done 卡汇总，对 failed/crashed 标记【不可用】。
输出分类(🔴/🟡/🟢)和矛盾仲裁。"""
)

# 4. Read the synthesis card result via kanban_show()
```

**Important — results are NOT auto-pushed.** `kanban_complete` summary does not auto-return to the calling agent. You must periodically `kanban_show(<task_id>)` to check card status and read completed summaries.

**⚠ Worker failure handling (parent-free mode):**
Since the synthesis card has NO parents, it runs immediately regardless of worker status. The orchestrator uses `kanban show` to read each worker. Workers that crashed show as `failed` — the orchestrator skips them and synthesizes with available results. **No deadlock possible.**

For the rare case of orchestrator self-crash (its model fails mid-run): use `kanban show t1/t2/t3` manually and synthesize yourself. This is faster than creating a fallback card.

**Prerequisites**: Gateway running (`hermes gateway status`), Kanban initialized, each worker profile configured with its target model.

### Dispatch Pattern — delegate_task (single-model fallback)

Use when all sub-agents can share the same model (no multi-model requirement), or when Kanban is unavailable:
```python
# Batch 1: send 3 together
delegate_task(tasks=[
    {"goal": "...architect...", "context": "...", "role": "leaf"},
    {"goal": "...analyst...", "context": "...", "role": "leaf"},
    {"goal": "...PM...", "context": "...", "role": "leaf"},
])
# Then separately send the 4th
delegate_task(tasks=[{"goal": "...ops...", "context": "...", "role": "leaf"}])
```

## Design Mode: From Investment Philosophy to System Architecture

When the user has an investment philosophy (not a concrete proposal), use **Design Mode** instead of evaluation mode. The same 4 agents take different roles:

### When To Use Design Mode

- User says "I want to build a system based on X philosophy"
- User describes their trading intuition (e.g. "short-term = sentiment + money flow, long-term = value reversion")
- User says "forget my previous approach, let's start fresh from this concept"
- User wants to explore feasibility before committing to implementation

### Design Mode Role Redefinition

| Role | Design Focus | Key Questions |
|------|-------------|---------------|
| 🏛️ **System Architect** (DeepSeek perspective) | Overall architecture, data flow, layer decomposition | How to translate this philosophy into 3-5 decision layers? What data flows between them? Existing assets vs gaps? |
| 📊 **Trend Analyst** (Kimi perspective) | Layer-1 detail: market-wide signals | How to measure market temperature? Which indices, which capital flows, which sentiment indicators? Weighting scheme? |
| 🔄 **Sector Strategist** (GLM perspective) | Layer-2 detail: sector rotation + stock selection | How to detect hot sectors? How to identify leaders? What confirms persistence vs one-day pump? |
| 🛡️ **Auditor / Risk Architect** (MiniMax perspective) | Layer-3 detail: valuation gating, risk controls, full roadmap | How to integrate existing valuation data? Stop-loss design? Iteration phases? What blind spots exist? |

### Design Mode Dispatch Process

**1. Prepare comprehensive context inventory** — before dispatching, gather:
- Complete database table inventory (name, row count, date range)
- Current cron job list (name, schedule, script, status)
- Available skills relevant to the domain
- Existing factor/signal tables with their fields
- Any prior system architecture or strategy documents

This inventory is fed to ALL agents so they design against real data, not assumptions.

**2. Dispatch 4 agents with layer-scoped goals** — each agent focuses on ONE layer/angle:

```python
# First dispatch (architecture umbrella)
delegate_task(
    goal="Design complete system architecture for [philosophy]",
    context="Full system inventory + philosophy description"
)
# Then batch the 3 layer-specific agents
delegate_task(tasks=[
    {"goal": "Design Layer-1: market temperature...", "context": "..."},
    {"goal": "Design Layer-2: sector rotation...", "context": "..."},
    {"goal": "Design Layer-3: valuation integration + risk + roadmap...", "context": "..."},
])
```

**3. Data gap discovery is critical** — the most common failure mode of design-by-agent is assuming data exists. Each agent MUST:
- Name the specific tables/columns they need
- The architect checks all tables exist
- If data is missing, flag as P0/P1/P2 gap
- Results saved to disk so the user can review later

**4. Synthesize the 3-layer architecture** — after all agents return:
- Build a **consensus layer diagram** showing data flow between layers
- Create a **data dependency matrix** (which existing tables feed which layer)
- List **P0 gaps** (must-fix-before-starting) vs **P1 gaps** (fix-during-implementation)
- Generate a **phased iteration plan** with concrete tasks and acceptance criteria

### The 3-Layer Framework Template (A-Share Focus)

This is the canonical architecture that emerged from the user's philosophy. Save as a template for future design sessions:

```
Layer 1: Market Temperature (大盘温度)
  Input: index_daily, market_moneyflow, hsgt_moneyflow, limit_up_pool
  Output: position_ratio (0%~100%)
  Sub-factors: index_trend(35%) + capital_flow(35%) + sentiment(30%)

Layer 2: Sector Rotation (板块轮动)
  Input: sector_moneyflow_ths/moneyflow_ind_ths, ths_member, limit_up_pool
  Output: top_N_sectors + leader_stocks
  Sub-factors: consecutive_moneyflow(40%) + stock_alignment(30%) + leader_strength(30%)

Layer 3: Valuation Gate (估值门控)
  Input: valuation_results(channel_position), daily_kline
  Output: buy/hold/reduce/sell signal per stock
  Gating: channel_position>85% → reject buy, channel_position<35% → prefer buy
```

### Design Mode Pitfalls

- **"Zero new data" is a trap**: One agent may claim no data gaps. Cross-check by having each agent independently verify the tables they need against the actual DB. This session's GLM agent discovered `ths_member` was missing while the architect claimed "zero new data needed."
- **Save design docs to disk**: Use `docs/` directory so the user can review asynchronously. Each document should be self-contained.
- **User philosophy may be contradictory**: Users often say "I want X and Y" where X and Y conflict (e.g. short-term trading + long-term value). Flag contradictions explicitly.
- **Language matters**: If the user writes in Chinese, pass `respond in Chinese` to all sub-agents or the default English summaries will contaminate the synthesis.
- **Gap prioritization**: Not all data gaps are equal. `ths_member` makes L2 impossible (P0). Two-rong margin is nice-to-have for L1 (P1). Don't let the user get blocked by P1 gaps.
- **Data freshness check**: A table with 1000 rows `WHERE date = MAX(date)` being only 3 days old means insufficient history. Always check `MIN/MAX(date)`.
- **Data gap reference file**: See `references/data-gap-discovery.md` for the full gap analysis methodology and the specific gaps found in this session (ths_member missing, sector moneyflow history insufficient, etc.).

## Synthesis & Reporting Pattern

After all 4 agents return, synthesize in this order:

### 1. Consensus Table
| Topic | Architect | Analyst | PM | Ops |
|-------|:---------:|:-------:|:--:|:---:|

### 2. Disagreement Resolution
For each disagreement:
- State each agent's position and their reasoning
- **Dig into the root cause** — often disagreements come from different assumptions about the same thing (e.g., "valuation is urgent" assumes `fina_indicator` data source, but a lighter `daily_basic` alternative resolves it)
- Propose a resolution that reconciles both positions
- Sometimes the disagreement reveals a **third path** neither considered

### 3. Structured Roadmap
Organize into phases:
- **Zero-Day Actions** (~30 min): Quick fixes that clear blockers (DB PRAGMAs, cron bugs, backup restoration, chain confirmation)
- **Phase 1** (1-2 weeks): Core signal/strategy fix — the fundamental problem
- **Phase 2** (3-6 weeks): Output layer — make the system useful daily
- **Phase 3** (6-10 weeks): Decision loop — automation + learning from results

Each phase needs: goal, specific deliverables with acceptance criteria, and a "don't do" list.

### 4. Output Format Requirements
✅ **Must be detailed** — structured sections, tables with specific numbers, concrete file paths
✅ **Must resolve disagreements explicitly** — don't gloss over conflict, show the reasoning
❌ **No vague summaries** — the user called this out ("总结太笼统，缺失太多信息")
❌ **No glossing over risks** — be honest about what you don't know

## A-Share Quant Evaluation Checklist

When evaluating an A-share quantitative system, these are the specific things to check:

### Data Layer
- [ ] DB size and growth rate (6.9GB/year ~2.5GB growth)
- [ ] SQLite configuration (cache_size, mmap, journal_mode)
- [ ] WAL mode + PRAGMA settings
- [ ] Index coverage on key tables
- [ ] Data freshness (cron last_run_at timestamps)

### Cron Layer
- [ ] All cron jobs listed with their status
- [ ] "error" status jobs — diagnose: script bug vs actual failure
- [ ] Chain dependencies (kline → factors → signals)
- [ ] Backup cron — is it active? What's the recovery point?
- [ ] Hermes cron vs system crontab (Hermes cron dies with process)

### Factor Pipeline
- [ ] Actual computation chain (not just filenames — trace real imports)
- [ ] Any TODO/stub code that might indicate incomplete implementation
- [ ] checksum coverage across all dates
- [ ] Incremental vs backfill — two different paths may diverge

### Strategy Layer
- [ ] IC/ICIR values (direction matters — negative IC means the system is anti-signalling)
- [ ] Parameter sensitivity (small change → huge Sharpe swing = overfitting)
- [ ] Market state dependency (factor IC may flip sign between bull/bear/range-bound)
- [ ] A-share-specific: T+1 settlement, price limit circuit breakers, retail dominance

## Pitfalls

- **Kanban parents 死锁风险 (已在新流程中规避)**: CLI/Python示例已经不再使用`--parent`/`parents=[]`。如果你在旧代码中看到`parents=[...]`，任何worker崩溃会导致orchestrator永久等待。立即迁移到无parents模式：等待worker全部done→再创建orchestrator卡→orchestrator用kanban show读取结果。
- **结果不会自动回传**: Kanban card 的 `kanban_complete summary` 不会自动推送到母进程。必须通过 `kanban_show(task_id)` 手动拉取。多模型评估时需轮询检查各卡状态。
- **delegate_task ignores delegation config (已知Bug)**: `delegate_task` 会忽略 `delegation.model`/`delegation.provider` 配置，子代理全部继承母进程模型。需要多模型派发时必须使用 Kanban 方案。
- **batch size limit**: `delegate_task` max 3 concurrent children per user. Send 4th as separate call.
- **Sub-agent model**: children inherit parent model + fallback chain unless pinned in config. They default to English output unless you specify language in context.
- **4th agent ordering**: The "wait for all to complete" only works within a single batch. Send the 4th agent separately — its result arrives as its own message later, not grouped with the batch.
- **Too many topics in one evaluation**: Limits output quality. Keep the scope focused (e.g., "evaluate this proposed 3-layer quant architecture" — not "and also design the UI").
- **User language**: If the user writes in Chinese, pass `respond in Chinese` in the context to each subagent. Otherwise they default to English summaries.
-- **复核 each fix**: User requires verification (复核) after every change, with explicit confirmation before proceeding to the next item.
- **P0 issue taxonomy reference**: See `references/p0-issue-taxonomy.md` for the 7-category P0 classification system discovered during 4-model review. Use this as a checklist when auditing data infrastructure.
