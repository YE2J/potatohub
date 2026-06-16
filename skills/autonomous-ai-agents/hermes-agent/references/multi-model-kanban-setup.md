# Multi-Model Kanban Army Setup

## Architecture

```
default (deepseek-v4-pro) ── user-facing session
orchestrator (any model)  ── task decomposition + kanban creation
worker-*    (one per model) ── claim + execute kanban tasks
gateway dispatcher          ── scans kanban.db every 60s, spawns workers
```

## Setup Steps

### 1. Create worker profiles (one per model)
```bash
hermes profile create worker-glm --clone-from default
hermes config set model.provider z.ai --profile worker-glm
hermes config set model.default glm-5 --profile worker-glm
# Repeat for kimi, qwen, nvidia, etc.
```

### 2. Write SOUL.md for each worker (identity + expertise)
Each worker gets a distinct persona so the orchestrator can route tasks by domain:
- worker-glm → logical reasoning, data analysis
- worker-kimi → long documents, deep research
- worker-qwen → creative strategy, planning
- worker-nvidia → engineering, code implementation

### 3. Configure the orchestrator
```yaml
# In orchestrator's config.yaml
model:
  default: deepseek-v4-flash
  provider: deepseek
kanban:
  orchestrator_profile: orchestrator
  auto_decompose: true
platform_toolsets:
  cli:
    - kanban  # REQUIRED for task creation
```

### 4. Initialize kanban
```bash
hermes kanban init
hermes gateway start  # dispatcher runs inside gateway
```

### 5. Trigger decomposition
```bash
hermes -p orchestrator chat -q "请将以下任务分解并分配给合适的worker: ..."
```

## Pitfalls

1. **Delegation model not hot-reloadable**: Changing `delegation.provider` or `delegation.model` in config.yaml does NOT take effect mid-session. `delegate_task` caches the model at session start. Fix: restart session or use `hermes -p <profile> chat -q` via terminal instead.

2. **worker-glm base_url bug**: Cloned profiles may inherit `base_url` pointing to wrong provider. Check with `grep base_url` and clear if wrong.

3. **Worker .env**: Profiles cloned from default inherit all API keys, but profiles cloned from another worker only inherit that worker's keys. If a new worker needs a different provider's key, copy the line from default .env.

4. **Kanban tasks in 'ready' forever**: Gateway must be running for dispatcher to work. Check with `hermes gateway status`.
