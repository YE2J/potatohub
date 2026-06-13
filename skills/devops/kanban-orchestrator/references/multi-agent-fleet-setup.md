# Multi-Agent Kanban Fleet Setup

Reference: creating and wiring up the profiles that the orchestrator and dispatcher
will eventually route tasks to.

## Overview

Kanban is a **cross-profile** coordination system. At minimum you need:

1. **One or more worker profiles** that the dispatcher spawns
2. **An orchestrator profile** (optional, but recommended for project decomposition)
3. **The dispatcher** running in the gateway — loads skills and spawns workers

The default profile can serve as orchestrator, or you can create a dedicated one.

## Step-by-Step: Creating the Fleet

### 1. Check existing state

```bash
hermes profile list              # what exists already
```

### 2. Create profiles

```bash
# Worker profiles — clone from default to inherit API keys
hermes profile create worker-glm --clone
hermes profile create worker-kimi --clone
```

The `--clone` flag copies `config.yaml`, `.env`, and `SOUL.md` from the
current profile. Workers inherit the same credential pool (API keys stay in
`.env`), but get **fresh sessions, memory, and skills** — full isolation.

**Key:** if the default profile already has all the API keys you need
(e.g. `GLM_API_KEY`, `KIMI_CN_API_KEY`, `DEEPSEEK_API_KEY`), cloning
is the fastest path. Otherwise, edit each profile's `.env` separately.

### 3. Configure each worker's model

Use `hermes -p <profile>` since the wrapper scripts at `~/.local/bin/`
may not be on `PATH`:

```bash
# Worker A: GLM-4-Plus on Z.AI
hermes -p worker-glm config set model.default glm-4-plus
hermes -p worker-glm config set model.provider "z.ai"

# Worker B: Moonshot on Kimi
hermes -p worker-kimi config set model.default moonshot-v1-8k
hermes -p worker-kimi config set model.provider "kimi"

# Orchestrator (dedicated profile): keep DeepSeek (or whatever the default was)
hermes -p orchestrator config set model.default deepseek-v4-flash
hermes -p orchestrator config set model.provider deepseek
```

**Pitfall:** the wrapper shell scripts (`~/.local/bin/<profile-name>`)
may not be on the user's `PATH`. Always use `hermes -p <name>` until
you've verified the alias works.

### 4. Write SOUL.md for each profile

Each profile needs a role-defining SOUL.md so it knows how to behave
when the dispatcher spawns it:

**Orchestrator SOUL.md** — emphasises *route, don't execute*:

```markdown
# Orchestrator

You are the project orchestrator. Your job is NOT to do the work yourself:

1. Understand the user's project goal
2. Decompose into clear, independent tasks
3. Push tasks to the Kanban board with `kanban_create()`
4. Link dependencies so the dispatcher sequences work correctly
5. Report progress to the user

Available workers: worker-glm (GLM), worker-kimi (Kimi)
```

**Worker SOUL.md** — focuses on the Kanban lifecycle:

```markdown
# Worker — <Model Name>

You handle <domain> tasks: backend code, APIs, frontend, docs, etc.

Kanban lifecycle:
1. Dispatcher spawns you → `kanban_show()` to read the task body
2. Work inside `$HERMES_KANBAN_WORKSPACE`
3. `kanban_heartbeat()` if long-running
4. Complete: `kanban_complete(summary="...", metadata={...})`
5. Stuck: `kanban_comment()` + `kanban_block(reason="...")`
```

Write these files at `~/.hermes/profiles/<name>/SOUL.md` directly.

### 5. Initialize the kanban board

```bash
hermes kanban init
```

This creates the SQLite database (`~/.hermes/kanban.db`) and prints the
list of discovered profiles — confirm your three profiles appear.

### 6. Configure kanban dispatch

The dispatcher lives in the gateway. Defaults are usually fine, but
verify these in `~/.hermes/config.yaml`:

```yaml
kanban:
  dispatch_in_gateway: true       # must be true for auto-dispatch
  dispatch_interval_seconds: 60   # how often the dispatcher ticks
  failure_limit: 2                # consecutive spawn failures before block
  auto_decompose: true            # AI-powered task decomposition on create
  orchestrator_profile: orchestrator   # name of the orchestrator profile
```

`orchestrator_profile` tells the auto-decomposer which profile to
assign breakdown tasks to.

### 7. Verify the workers are reachable

Quick model smoke-test for each worker:

```bash
hermes -p worker-glm chat -q "确认模型工作正常"
hermes -p worker-kimi chat -q "确认模型工作正常"
```

### 8. Put it to work

```bash
orchestrator chat -q "我的项目需求是..."
# or
hermes -p orchestrator chat
```

The orchestrator splits the project into tasks and calls
`kanban_create(title=..., assignee="worker-glm")` for each lane. The
dispatcher picks up ready tasks on its next tick (up to 60s).

## Common pitfalls

- **Wrapper scripts not on PATH.** The `hermes profile create` command
  creates `~/.local/bin/<name>`. If that directory isn't in `PATH`, the
  alias won't work. Use `hermes -p <name>` instead.
- **Missing API key in worker profile.** If you cloned from default but
  the default didn't have the right provider's key, the worker will fail
  silently at spawn time. Check each profile's `.env` before putting
  work on the board.
- **Dispatcher spawn fails silently.** A task in `ready` that never
  transitions to `running` means the dispatcher can't spawn the
  assignee profile. Common causes: profile doesn't exist, profile name
  has a typo, or the dispatcher isn't running (gateway down).
- **Kanban board not initialized.** The kanban tools fail if `kanban init`
  was never called. Run it once per machine.
- **over-linking.** Not every "and" is a dependency. Only `parents=[]`
  when a task truly cannot start without its predecessor's output.
