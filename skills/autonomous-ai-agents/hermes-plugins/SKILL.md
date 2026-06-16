---
name: hermes-plugins
description: "Develop, troubleshoot, and extend Hermes Agent via its plugin system. Covers plugin structure, diagnosis, registration patterns, and bridging Python packages to agent tools."
version: 1.0.0
author: Hermes Agent
tags: [hermes, plugins, troubleshooting, development, tool-registration]
---

# Hermes Agent Plugin Development & Troubleshooting

Hermes Agent's plugin system allows extending the agent with custom tools, hooks, CLI commands, and provider backends. Plugins live in `~/.hermes/plugins/<name>/` (user) or `<repo>/plugins/<name>/` (bundled).

## Plugin Structure

Every directory plugin must contain two files:

```
~/.hermes/plugins/<name>/
├── plugin.yaml          # Manifest: name, version, tools, hooks
└── __init__.py          # Entry point: MUST define register(ctx)
```

### `plugin.yaml`

```yaml
name: my-plugin
version: "1.0.0"
description: What my plugin does
author: Your Name
hermes_version: ">=0.26.0"
tools:                    # Optional: tool names to register
  - my_tool_name
hooks:                    # Optional: hook names to register
  - post_tool_call
```

### `__init__.py`

Must contain a `register(ctx)` function. The `ctx` is a `PluginContext` with these key methods:

| Method | Purpose |
|--------|---------|
| `ctx.register_tool(name, toolset, schema, handler, ...)` | Register an agent tool |
| `ctx.register_hook(name, handler)` | Register a lifecycle hook |
| `ctx.register_cli_command(name, help, setup_fn, handler_fn)` | Register a CLI subcommand |
| `ctx.llm` | Access the host-owned LLM facade |

## Diagnosing Plugin Loading Failures

When a plugin fails to load, check these locations in order:

### 1. Plugin loading warnings

```bash
grep "Failed to load plugin" ~/.hermes/logs/errors.log
# Or in agent.log:
grep "Failed to load plugin" ~/.hermes/logs/agent.log
```

Common error patterns:
- `No module named '<name>'` — the Python package the plugin depends on is not installed
- `ImportError` — missing dependency or broken import chain

### 2. Check enabled/disabled state

```bash
hermes plugins list                    # Full table with status
hermes plugins list --plain --no-bundled  # Compact user plugins only
```

### 3. Verify the plugin package is installed

If the plugin's `__init__.py` does `from some_package.plugin_core import register`, ensure `some_package` is installed in the Hermes venv:

```bash
~/.hermes/hermes-agent/venv/bin/pip show some_package
~/.hermes/hermes-agent/venv/bin/python3 -c "import some_package; print(some_package.__file__)"
```

### 4. After fixing, restart the gateway

```bash
hermes gateway restart
sleep 3
grep "plugin registered" ~/.hermes/logs/agent.log   # Confirm registration
```

## Tool Registration Pattern

```python
def register(ctx) -> None:
    ctx.register_tool(
        name="my_tool",
        toolset="my-toolset",           # Groups tools in hermes tools list
        schema={
            "name": "my_tool",
            "description": "What the tool does",
            "parameters": {
                "type": "object",
                "properties": {
                    "param1": {
                        "type": "string",
                        "description": "Parameter description",
                    },
                },
                "required": ["param1"],
            },
        },
        handler=_handle_my_tool,        # Callable(args: dict, task_id: str = None) -> str (JSON)
        description="Short description",
        emoji="🔧",                      # Display emoji in tools list
    )
```

Handler signature:
```python
def _handle_my_tool(args: dict, task_id: str = None) -> str:
    return json.dumps({"success": True, ...})
```

## Hook Registration Pattern

```python
def _post_tool_call_hook(ctx, tool_name: str, args: dict, result: str, duration: float) -> None:
    """Called after every tool execution. Non-blocking."""
    pass

def register(ctx) -> None:
    ctx.register_hook("post_tool_call", _post_tool_call_hook)
```

Valid hooks: `post_tool_call`

## Bridging Python Packages to Plugins

When a plugin wraps an existing Python package (not written as a Hermes plugin), the common pattern is:

1. Install the package into the Hermes venv: `~/.hermes/hermes-agent/venv/bin/pip install <package>`
2. Create the plugin directory with `plugin.yaml` + `__init__.py`
3. The `__init__.py` forwards to the package: `from mypackage.plugin_core import register`
4. Create `plugin_core.py` inside the package that implements `register(ctx)`
5. Inside `plugin_core.py`, use `ctx.register_tool(...)` to expose package functions as agent tools

### Pitfalls

- **Packages installed system-wide are invisible to Hermes** — always install into `~/.hermes/hermes-agent/venv/bin/pip`
- **`plugin_core.py` may not exist in the upstream repo** — the GitHub repo may be a CLI tool, not a plugin. You'll need to create this file yourself as a bridge
- **Plugin tools are session-scoped** — `/reset` is needed for new tools to appear after registration
- **After changing plugin code**, restart the gateway: `hermes gateway restart`
- **Logs are the canonical source** — `hermes doctor` won't report plugin loading failures as "issues"

## References

For session-specific detail, error transcripts, and reproduction recipes:
- `skill_view(name="hermes-plugins", file_path="references/hermes-evolution-fix.md")` — the hermes-evolution plugin fix case study
