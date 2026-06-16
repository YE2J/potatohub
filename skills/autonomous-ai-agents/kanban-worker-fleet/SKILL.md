---
name: kanban-worker-fleet
description: Set up and manage a fleet of Hermes worker profiles with different LLM backends, connected through the Kanban system for automatic task decomposition and distribution.
version: 1.0.0
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
  ├── worker-kimi    (Kimi K2.6)      — 研究员：深度搜索、多源分析、长文档、研究报告
  └── worker-glm     (GLM-5)          — 工匠：代码实现、代码审查、结构化输出、精准执行
```

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
# GLM (智谱) — latest: glm-5
# Confirmed working via z.ai provider. Clear base_url (cloned profiles may inherit wrong endpoint).
hermes config set model.provider z.ai --profile worker-glm
hermes config set model.default glm-5 --profile worker-glm
hermes config set model.base_url '' --profile worker-glm

# Kimi (Moonshot) — latest: kimi-k2.7-code
# kimi-k2.6 is deprecated (May 2026). kimi-k2-thinking does NOT exist (returns 404).
# kimi-k2.7-code is the newest coding model available via API.
hermes config set model.provider kimi-coding-cn --profile worker-kimi
hermes config set model.default kimi-k2.7-code --profile worker-kimi

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
for p in worker-glm worker-kimi; do
  echo "=== $p ===" && hermes -p "$p" chat -q "只回OK" 2>&1 | tail -3
done
# Each line should show "Messages: 2 (1 user, 0 tool calls)" = success
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

### Kimi model not found (kimi-k2-thinking)

`kimi-k2-thinking` does NOT exist as an API model. The available Kimi models via `kimi-coding-cn` provider are:
- `kimi-k2.6` — general-purpose multimodal (discontinued May 2026, still works)
- `kimi-k2.7-code` — latest coding-specific model

Use `kimi-k2.7-code` for the newest model. The "thinking" variant name is misleading — it's not an API endpoint.

### Dispatcher not picking up tasks

Check:
1. Gateway is running: `hermes gateway status`
2. Kanban is initialized: `hermes kanban list` should work
3. Tasks are in `ready` state (not `todo` with unmet dependencies)
4. The worker profile's model actually works (test with `hermes -p <worker> chat -q "test"`)

### Orchestrator lacks kanban tools

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
