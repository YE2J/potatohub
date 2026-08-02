---
name: kanban-worker-fleet
description: Set up and manage a fleet of Hermes worker profiles with different LLM backends, connected through the Kanban system for automatic task decomposition and distribution.
version: 1.1.0
author: Hermes Agent
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [kanban, multi-agent, orchestration, profiles, workers]
    related_skills: [hermes-agent]
---

# Kanban Worker Fleet

Set up multiple Hermes worker profiles — each backed by a different LLM provider/model with a distinct identity and specialization — wired through the Kanban system so complex tasks are automatically decomposed and distributed across your model fleet.

## When to Use

- You have API keys for 3+ LLM providers (DeepSeek, GLM, Kimi, Qwen, NVIDIA, etc.) and want them all to participate in tasks
- You want complex tasks automatically split by domain (research → Kimi, reasoning → GLM, coding → NVIDIA, etc.)
- You want a "fire and forget" workflow: send a task, have it auto-distributed, get results back

## Architecture

```
User (default profile)
  │
  ▼
Orchestrator (deepseek-v4-flash)
  │  Decomposes task → creates Kanban cards
  ▼
Kanban Board
  │  ready tasks picked up by dispatcher
  ▼
Workers (parallel execution)
  ├── worker-kimi     (Kimi K2.6)            — 研究员：搜索、分析、长文档、逻辑验证
  ├── worker-glm      (GLM-5.1)              — 工匠：代码实现、架构评审、结构化输出
  ├── worker-auditor  (MiniMax M2.7)         — 审计师：深度审计、交叉验证、性能安全
  └── worker-xiaomi   (MiMo v2.5)            — 实现者：代码验证、可行性与边界条件
```

### 4-Agent Code Review / Multi-Model Evaluation Pattern

This is a **verified workflow** (2026-07-09, expanded 2026-07-12) for multi-model parallel evaluation:

1. **Default profile** (you) drafts code or defines a task
2. **Create 4 Kanban cards** — one per worker profile, all with **no parents**
3. **Wait** for all workers to reach `done` status (check via `hermes kanban list`)
4. **Create synthesis card** — `assignee=orchestrator` with **NO `--parent` flag**. Body says `kanban show` each worker's results
5. Orchestrator runs → reads worker handoffs via `kanban show` → synthesizes → `kanban_complete`
6. **You read the result** via `kanban_show(<synthesis_task_id>)` — results are NOT auto-pushed

**CRITICAL: Do NOT use `parents=[t1,t2,t3]` on the synthesis card.**
Any worker crash → synthesis card deadlocks forever. The parent-free pattern above avoids this entirely.

**Typical latency:**
- GLM-5.1: ~68s (code tasks)
- Kimi K2.6: ~172s (research tasks)
- MiniMax M2.7: ~80-118s (audit tasks)
- MiMo v2.5: ~30-60s (lightning fast, code tasks)
- Dispatch cycle: up to 60s before gateway picks up new cards
- Total code review roundtrip: ~3-6 minutes (4 workers + synthesis)

## Setup Steps

### 1. Verify API keys are recognized

```bash
hermes auth list
# Each provider should show as active (← marker, not "auth failed")
```

### 2. Create worker profiles

```bash
# Clone from an existing profile to inherit config and .env
hermes profile create worker-glm --clone-from default
hermes profile create worker-kimi --clone-from default
hermes profile create worker-qwen --clone-from default
hermes profile create worker-nvidia --clone-from default
```

### 3. Configure each worker's model

```bash
# GLM (智谱) — current: glm-5.1
# Confirmed working via z.ai provider. Clear base_url (cloned profiles may inherit wrong endpoint).
hermes config set model.provider z.ai --profile worker-glm
hermes config set model.default glm-5.1 --profile worker-glm
hermes config set model.base_url '' --profile worker-glm

# Kimi (Moonshot) — current: kimi-k2.6
# Available: kimi-k2.6 (general multimodal), kimi-k2.7-code (newest coding), kimi-k2.7-code-highspeed
# ⚠ Provider name must be 'kimi-custom' (NOT 'kimi-coding-cn'). The latter fails with HTTP 401
# even with a valid API key. 'kimi-custom' reads inline api_key from providers.kimi-custom.api_key.
hermes config set model.provider kimi-custom --profile worker-kimi
hermes config set model.default kimi-k2.6 --profile worker-kimi
hermes config set model.base_url https://api.moonshot.cn/v1 --profile worker-kimi
hermes config set providers.kimi-custom.base_url https://api.moonshot.cn/v1 --profile worker-kimi

# MiniMax Auditor — minimax-m2.7
hermes profile create worker-auditor --clone-from default
hermes config set model.provider minimax --profile worker-auditor
hermes config set model.default minimax-m2.7 --profile worker-auditor
# Optionally write SOUL.md: cp ~/.hermes/skills/autonomous-ai-agents/minimax-auditor/SKILL.md ~/.hermes/profiles/worker-auditor/SOUL.md

# Xiaomi MiMo — mimo-v2.5
# Plugin: hermes-agent/plugins/model-providers/xiaomi (built-in)
# ⚠ supports_health_check=False → hermes status does NOT show this provider even when key is valid
hermes profile create worker-xiaomi --clone-from default
hermes config set model.provider xiaomi --profile worker-xiaomi
hermes config set model.default mimo-v2.5 --profile worker-xiaomi
hermes config set model.base_url '' --profile worker-xiaomi
# Write SOUL.md for reviewer identity

# worker-qwen and worker-nvidia were removed 2026-06-16 (per user request).
# To re-add them, create profiles and configure as documented in git history.
```

### 4. Write SOUL.md for each worker

Each worker needs a distinct identity with clear specialization. Write `~/.hermes/profiles/<worker>/SOUL.md` with:
- Name and model identity
- Specialized domain
- Communication style
- Language preference

See `references/worker-souls.md` for the full templates used in this setup.

### 5. Configure the orchestrator

```bash
hermes profile create orchestrator --clone-from default
hermes config set model.provider deepseek --profile orchestrator
hermes config set model.default deepseek-v4-flash --profile orchestrator
```

Write `~/.hermes/profiles/orchestrator/SOUL.md` describing its role as task decomposer and distributor.

### 6. Enable Kanban in the default profile

```yaml
# In ~/.hermes/config.yaml:
kanban:
  orchestrator_profile: orchestrator
  auto_decompose: true
  dispatch_in_gateway: true
  dispatch_interval_seconds: 60
```

### 7. Initialize Kanban

```bash
hermes kanban init
# Discovers all profiles automatically
```

### 8. Ensure gateway is running

```bash
hermes gateway status
# If stopped: hermes gateway start
# The gateway hosts the kanban dispatcher
```

## Verification

### Quick connectivity test per worker

```bash
# Test each worker individually (parallel loops on macOS are unreliable — no `timeout` command, and shell backgrounding can cause timeouts)
for p in worker-glm worker-kimi worker-auditor worker-xiaomi; do
  echo "=== $p ===\n$(hermes -p "$p" chat -q "只回OK" 2>&1 | tail -3)"
  echo ""
done
# If 1 message or error text: check provider/key/model.

### End-to-end test

```bash
# Trigger the orchestrator with a complex task
hermes -p orchestrator chat -q "将以下任务分解并分配给合适的worker：分析A股最近一周走势并给出投资建议"
```

Then check the board:

```bash
hermes kanban list
# Should show tasks with status: ready → running → done
```

## Pitfalls

### delegate_task ignores delegation config (Hermes bug)

`delegate_task` does NOT read from the `delegation.model` / `delegation.provider` config section. It appears to hardcode the subagent model to whatever was active at session start, ignoring later config changes and the explicit delegation settings.

**Symptoms:**
- `delegate_task` uses `qwen-plus` even when `delegation.model: deepseek-v4-pro`
- Error 401 if the hardcoded model's key is invalid
- `/reset` does NOT fix it — the bug persists across sessions

**Workaround A** — Use `terminal` to spawn worker profiles directly:
```bash
# Parallel execution with individual model control
hermes -p worker-glm chat -q "analyze financial data" 2>&1 &
hermes -p worker-kimi chat -q "research company history" 2>&1 &
wait
```

In Python via execute_code:
```python
from hermes_tools import terminal
terminal("hermes -p worker-glm chat -q '...' ", background=True, notify_on_complete=True)
terminal("hermes -p worker-kimi chat -q '...' ", background=True, notify_on_complete=True)
```

**Workaround B** — Use the Kanban system (gateway dispatcher spawns profiles directly):
```bash
hermes -p orchestrator chat -q "decompose and distribute this task..."
```

The Kanban dispatcher bypasses `delegate_task` entirely — it spawns worker profiles natively, so this bug doesn't affect it.

### Wrong base_url in cloned profiles

When cloning a profile, the `model.base_url` may point to the source profile's provider API. **Always clear or correct base_url** for each worker:

```bash
hermes config set model.base_url '' --profile worker-glm
```

Symptom: API calls fail with authentication errors even though the key is valid, because requests are sent to the wrong endpoint.

### DashScope China endpoint: env var vs direct api_key

The `alibaba` provider may not resolve `DASHSCOPE_API_KEY` from `.env` correctly when using a China-endpoint key. If 401 persists even with correct base_url and valid key:

```bash
# Set the key directly in model config (not env)
hermes config set model.api_key "sk-..." --profile worker-qwen
```

Alternatively use `execute_code` to inject the key into config.yaml because `hermes config set` may redact long secret values. See `references/dashscope-china-endpoint.md` for full diagnostic steps.

### API key not inherited

Cloned profiles get their own `.env` copy at clone time. If you add new API keys to the default `.env` later, they won't propagate to existing profiles. **Re-clone or manually sync** the `.env` file.

### Expired/invalid API keys

Run `hermes auth list` to check credential health. A `(re-auth may be required)` note or `auth failed` status means the key needs renewal.

### Qwen/DashScope account arrears

If ALL DashScope models (including previously-working ones like `qwen-plus`) suddenly return HTTP 400 "Arrearage — Access denied, account not in good standing": the account has overdue payment. Even models that were free-tier may be blocked. Top up at https://dashscope.aliyun.com/. After recharge, `qwen3.7-max` should work immediately.

### Kimi provider name must be `kimi-custom`

The provider name `kimi-coding-cn` is NOT recognized by Hermes for API key resolution. Even with a valid inline key in `providers.kimi-coding-cn.api_key`, calls return HTTP 401.

**Fix:** Use `kimi-custom` as the provider name instead:
```bash
hermes config set model.provider kimi-custom --profile worker-kimi
hermes config set providers.kimi-custom.api_key 'sk-...' --profile worker-kimi
hermes config set providers.kimi-custom.base_url https://api.moonshot.cn/v1 --profile worker-kimi
```

**Available Kimi models (verified 2026-07-12):**
- `kimi-k2.6` — general multimodal with reasoning, 262K context
- `kimi-k2.5` — previous generation
- `kimi-k2.7-code` — latest coding-specific model
- `kimi-k2.7-code-highspeed` — high-speed variant of k2.7-code
- Various `moonshot-v1-*` legacy models

`kimi-k2.6` is still fully operational (confirmed working).

### Dispatcher not picking up tasks

Check:
1. Gateway is running: `hermes gateway status`
2. Kanban is initialized: `hermes kanban list` should work
3. Tasks are in `ready` state (not `todo` with unmet dependencies)
4. The worker profile's model actually works (test with `hermes -p <worker> chat -q "test"`)

### Worker crashes silently (protocol violation)

Kimi K2.7-code has been observed to exit without calling `kanban_complete` or `kanban_block` (protocol violation), leaving the task `running` until the claim TTL expires. The dispatcher then retries (up to `failure_limit`). If the second retry also crashes, the task is marked `failed`.

**Symptom:** `kanban show <task_id>` shows run outcome "worker exited cleanly (rc=0) without calling kanban_complete or kanban_block — protocol violation"

**Impact:** If the synthesis card has `parents` dependency on the failed card, it stays `todo` forever. The parent task is NOT auto-promoted.

**Fix (proactive — prevent the crash):** Add `fallback_providers` to `~/.hermes/profiles/worker-kimi/config.yaml`:
```yaml
fallback_providers:
  - provider: deepseek
    model: deepseek-v4-flash
  - provider: deepseek
    model: deepseek-v4-pro
```
When Kimi crashes, the dispatcher auto-falls back to DeepSeek for that card. Output quality differs but the review completes instead of deadlocking.

**Fix (reactive — after crash):** `kanban_reclaim <failed_task_id>` to retry, or create a new synthesis card without parents using completed results only.

### `hermes status` misses some providers

Some providers have `supports_health_check=False` in their plugin definition, meaning `hermes status` (or `hermes auth list`) will NOT detect them even with a valid API key. This does NOT mean the provider is broken — the health check endpoint simply returns 401 even with a valid key.

**Affected providers:**
- **Xiaomi MiMo** (`xiaomi` provider, `XIAOMI_API_KEY`) — `/v1/models` returns 401 with valid key
- **Kimi CN** (`kimi-custom` provider, `KIMI_CN_API_KEY`) — uses `api.moonshot.cn`, doesn't show in default status check which only looks at `KIMI_API_KEY`. Old provider name `kimi-coding-cn` is broken for auth — do NOT use it.

**Diagnostic:** Test directly via curl:
```bash
# Xiaomi MiMo
curl -s https://api.xiaomimimo.com/v1/chat/completions \
  -H "Authorization: Bearer $XIAOMI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"mimo-v2.5","messages":[{"role":"user","content":"OK"}],"max_tokens":5}'

# Kimi CN
curl -s https://api.moonshot.cn/v1/chat/completions \
  -H "Authorization: Bearer $KIMI_CN_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"kimi-k2.7-code","messages":[{"role":"user","content":"OK"}],"max_tokens":5}'
```
A valid response (non-401) confirms the key works.

### 60s dispatch interval latency

The gateway dispatcher runs on a `dispatch_interval_seconds` cycle (default 60s). New `ready` cards are not picked up immediately — they wait for the next tick. Combined with worker execution time (~1-3min), total round-trip for a 3-worker + synthesis workflow is ~3-5 minutes. Not suitable for quick iteration.

**Speed-up: change to 15s:**
```yaml
# ~/.hermes/config.yaml
kanban:
  dispatch_interval_seconds: 15
```
**⚠ Requires gateway restart to take effect.** Run `hermes gateway restart` from a terminal OUTSIDE the gateway process (not from inside a Hermes session, which will get killed by SIGTERM). Use a separate terminal window or `launchctl kickstart -k gui/$(id -u)/ai.hermes.gateway`.

The orchestrator profile needs `kanban` in its `platform_toolsets.cli` list to create tasks:

```bash
hermes config set platform_toolsets.cli '["browser","clarify","code_execution","computer_use","cronjob","delegation","file","image_gen","kanban","memory","messaging","session_search","skills","terminal","todo","tts","video","vision","web"]' --profile orchestrator
```

## Common Commands

```bash
hermes profile list                      # See all profiles and their models
hermes kanban list                       # View task board
hermes kanban tail <task_id>             # Watch task progress
hermes kanban archive <task_id>          # Clean up completed tasks
hermes gateway status                    # Check dispatcher health
grep kanban ~/.hermes/logs/gateway.log   # Dispatcher activity log
```

## References

- `references/kimi-cn-xiaomi-provider-quirks.md` — Kimi-CN endpoint model list, Xiaomi MiMo status-check blind spots, and setup quirks
- `references/worker-souls.md` — SOUL.md templates for each worker profile
- `references/dashscope-china-endpoint.md` — DashScope/alibaba China endpoint troubleshooting
