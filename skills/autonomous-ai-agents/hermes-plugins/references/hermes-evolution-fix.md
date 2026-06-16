# hermes-evolution Plugin Fix Case Study

## Problem

The `hermes-evolution` plugin (v7.0.13) was **enabled** but failed to load on every Hermes restart:

```
WARNING hermes_cli.plugins: Failed to load plugin 'hermes-evolution': No module named 'evolution'
```

## Root Cause (2 issues)

| # | Issue | Detail |
|---|-------|--------|
| 1 | **Package not installed** | The `evolution` Python package from `NousResearch/hermes-agent-self-evolution` was missing from the Hermes venv |
| 2 | **`plugin_core.py` never existed** | The plugin's `__init__.py` does `from evolution.plugin_core import register`, but the upstream GitHub repo (`hermes-agent-self-evolution`) is a **CLI tool**, not a plugin — it never shipped `plugin_core.py` |

## Fix

### Step 1: Install the evolution package

```bash
~/.hermes/hermes-agent/venv/bin/pip install \
  -e "git+https://github.com/NousResearch/hermes-agent-self-evolution.git@main#egg=hermes-agent-self-evolution"
```

This installs as editable (`-e`) so the `evolution/` package is linked from the clone at `~/.hermes/hermes-agent/venv/src/hermes-agent-self-evolution/`.

### Step 2: Create `evolution/plugin_core.py`

Created at:
```
~/.hermes/hermes-agent/venv/src/hermes-agent-self-evolution/evolution/plugin_core.py
```

This file implements `register(ctx)` registering **7 tools** and **1 hook**:

| Tool | What it does | Evolution package API used |
|------|-------------|--------------------------|
| `evolution_run_cycle` | Validate skill evolution setup (dry-run) | `evolution.skills.evolve_skill.evolve()` |
| `evolution_self_monitor` | Monitor agent metrics | Custom (log sizes, session counts) |
| `evolution_analyze_performance` | Analyze session traces | Custom (session file scan) |
| `evolution_create_tool` | Create new skill files | Custom (file write) |
| `evolution_learn` | Import session history | `evolution.core.external_importers.HermesSessionImporter.extract_messages()` |
| `evolution_memory_discover` | Explore memory files | Custom (directory scan) |
| `evolution_audit` | Audit all skills | Custom (skill directory scan) |
| **Hook**: `post_tool_call` | Log tool execution | `logging` |

### Step 3: Restart gateway

```bash
hermes gateway restart
# Then verify:
grep "plugin registered" ~/.hermes/logs/agent.log
# Expected: "evolution.plugin_core: hermes-evolution plugin registered: 7 tools + 1 hook"
```

## Testing

All 7 tools + 1 hook tested via Python test harness:

| Test | Result |
|------|--------|
| `evolution_run_cycle` with real skill `test-driven-development` | ✅ Dry-run validated (9,528 chars, DSPy+GEPA ready) |
| `evolution_self_monitor` | ✅ Returns session/log metrics |
| `evolution_analyze_performance` | ✅ Scans session files |
| `evolution_create_tool` | ✅ Creates SKILL.md files |
| `evolution_learn` | ✅ Uses `HermesSessionImporter.extract_messages()` |
| `evolution_memory_discover` | ✅ Finds 4 memory files |
| `evolution_audit` | ✅ Lists 87 skills (985KB) |
| `post_tool_call` hook | ✅ Executes without error |
| `register()` signature | ✅ Matches `PluginContext` API |
| CLI `python -m evolution.skills.evolve_skill --dry-run` | ✅ Full pipeline validated |

## Key Architectural Insight

The `hermes-agent-self-evolution` GitHub repo is a **standalone CLI tool** (`python -m evolution.skills.evolve_skill`) — it was never designed as a Hermes plugin. The `hermes-evolution` plugin at `~/.hermes/plugins/hermes-evolution/` is a separate wrapper that bridges CLI capabilities into agent-accessible tools. The `plugin_core.py` was the missing interface layer.

To run a real (non-dry-run) evolution:

```bash
cd ~/.hermes/hermes-agent/venv/src/hermes-agent-self-evolution
HERMES_AGENT_REPO=~/.hermes/hermes-agent \
  ~/.hermes/hermes-agent/venv/bin/python3 -m evolution.skills.evolve_skill \
  --skill <name> --iterations 10 --eval-source synthetic
```

Note: requires the evolution package's optimizer model (default `openai/gpt-4.1`) to be accessible — this is separate from the user's Hermes model.
