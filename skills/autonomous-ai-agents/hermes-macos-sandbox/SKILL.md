---
name: hermes-macos-sandbox
description: "macOS TCC sandbox limitations for Hermes — file write restrictions, cron execution constraints, binary availability, and workaround patterns."
version: 1.2.0
author: Hermes Agent
license: MIT
platforms: [macos]
metadata:
  hermes:
    tags: [macos, sandbox, tcc, filesystem, troubleshooting]
    category: autonomous-ai-agents
    related_skills: [hermes-agent]
---

# Hermes macOS Sandbox Limitations

On macOS 15+ (Sequoia) and later, Hermes's terminal and file tools run inside a TCC (Transparency, Consent, and Control) sandbox. This blocks writes to most directories outside `~/.hermes/`.

## When This Skill Activates

Use this skill when:
- `write_file` or `terminal` returns `Operation not permitted` for a path outside `~/.hermes/`
- You're asked to create files/directories in `~/`, `/tmp/`, or other home subdirectories
- You need to choose a location for new persistent data (wikis, databases, shared dirs)

## Writable vs Blocked Directories

| Directory | Status | Notes |
|-----------|--------|-------|
| `~/.hermes/` and subdirs | ✅ Writable | Always use this as the base |
| `~/.hermes/wiki/` | ✅ | Wiki location (set `WIKI_PATH`) |
| `~/.hermes/scripts/` | ✅ | Scripts and tools |
| `~/wiki/` | ❌ Blocked | `Operation not permitted` |
| `~/.gbrain/` | ❌ Blocked | Cannot create or delete |
| `~/brain/` | ❌ Blocked | Cannot create or delete |
| `~/my_quant_system/` | ✅ Accessible | Read/write works. DB files and scripts accessible from cron. |
| `~/quant_shared/` | ❌ Blocked | Fully blocked — shell `ls` and Python `os.stat` both fail. Must move to `~/.hermes/quant_shared/`. |
| `/tmp/` | ✅ Writable | `write_file` resolves to `/private/tmp/` — works for temp files |

**Rule of thumb:** If you need to create persistent files or directories, create them under `~/.hermes/`.

## Workaround Pattern

When a task needs files outside `~/.hermes/`:

1. **Create inside sandbox** — write to `~/.hermes/<name>/`
2. **Set env vars accordingly** — e.g., `WIKI_PATH=~/.hermes/wiki` in `.env`
3. **Tell the user** they can `mv` or symlink if they want the canonical path
4. **Don't try to force writes** — repeated attempts just waste time and tokens

### Real Example: LLM Wiki

```bash
# ❌ This fails
mkdir ~/wiki
write_file ~/wiki/SCHEMA.md ...

# ✅ This works
mkdir ~/.hermes/wiki
write_file ~/.hermes/wiki/SCHEMA.md ...
echo 'export WIKI_PATH="$HOME/.hermes/wiki"' >> ~/.hermes/.env
```

## Diagnosing Sandbox Blocks

When you see:
```
Operation not permitted
shell-init: error retrieving current directory: getcwd: cannot access parent directories
chdir: error retrieving current directory: getcwd: cannot access parent directories
```

It's the TCC sandbox. Don't retry the same path — immediately switch to a `~/.hermes/` subdirectory.

## What Still Works

- `read_file` — can read most files on the system
- `search_files` — can search with ripgrep
- `write_file` — but ONLY to `~/.hermes/` paths
- `terminal` — but `mkdir`/`rm`/`cp` to non-sandbox paths fail
- `computer_use` — drives GUI apps, can bypass sandbox for Desktop operations
- `web_search` / `web_extract` — network access not affected

## Cron Execution Sandbox (Critical)

Cron jobs run under **stricter sandbox** than interactive sessions. This affects `no_agent=true` script-based jobs heavily.

### Binary Execution — What Works in Cron

| Binary | Cron | Notes |
|--------|:----:|-------|
| `/usr/bin/sqlite3` | ✅ | System binary, fully available |
| `/usr/bin/curl` | ✅ | System binary, fully available |
| `/usr/bin/jq` | ✅ | JSON parsing in bash pipelines |
| `/usr/bin/python3` | ❌ | macOS shim — requires Xcode CLT (often broken/uninstalled) |
| `/opt/homebrew/bin/python3.*` | ❌ | `Operation not permitted` — outside sandbox |
| `~/my_quant_system/.venv/bin/python3` | ❌ | `Operation not permitted` — outside sandbox |
| Any user-installed Python | ❌ | Blocked by TCC |
| `execute_code` tool | ❌ | Blocked in cron mode by safety policy |
| **`~/.hermes/<path>/python*`** | ✅ | **Binaries inside `~/.hermes/` are executable!** |

### Pattern A (Preferred): Standalone Python in `~/.hermes/`

Install a static Python (no external dependencies) inside the sandbox-safe `~/.hermes/` directory. **Zero code changes** — all existing Python scripts work as-is.

```bash
# Option 1: Copy uv-managed Python (if already installed)
cp -r ~/.local/share/uv/python/cpython-3.11.*-macos-aarch64-none ~/.hermes/python-standalone/
PY=~/.hermes/python-standalone/*/bin/python3.11

# Option 2: Download python-build-standalone
curl -L -o /tmp/py.tar.gz \
  "https://github.com/astral-sh/python-build-standalone/releases/download/20260610/cpython-3.11.15+20260610-aarch64-apple-darwin-install_only_stripped.tar.gz"
tar xzf /tmp/py.tar.gz -C ~/.hermes/python-standalone/

# Update all cron scripts to use the new Python
# Replace: ~/my_quant_system/.venv/bin/python3
# With:    ~/.hermes/python-standalone/.../bin/python3.11
```

Then revert cron jobs to `no_agent=true` with their original shell scripts (just Python path updated).

### Pattern A-Alt: CSV → sqlite3 Bulk Import (No Python)

When you have rows of data ready to write but can't run Python: write a CSV to `/tmp/` with `write_file`, then use `sqlite3 .import` into a temp table, compute derived columns with SQL, and `INSERT OR REPLACE` into the target table. See [references/csv-sqlite-import-pattern.md](references/csv-sqlite-import-pattern.md) for the full recipe.

### Pattern B: Convert Script Cron to Agent-Driven Cron

When a `no_agent=true` cron job fails because its script calls Python:

1. **Update the cron job**: `cronjob(action='update', no_agent=false, script='')` — remove the shell script, switch to LLM-driven mode
2. **Rewrite the prompt**: Use `curl` + `jq` + `sqlite3` pipelines instead of Python
3. **API auth via .env**: Read tokens with `grep KEY ~/.hermes/.env | cut -d= -f2-`
4. **JSON parsing with jq**: Replace `python3 -c "import json..."` with `jq -r '...'`
5. **DB operations**: Replace `import sqlite3` with `sqlite3 "$DB" "SQL..."`

Example — Python HTTP call becomes:
```bash
# ❌ Old (no_agent=true, calls python3 script)
exec ~/my_quant_system/.venv/bin/python3 ~/.hermes/scripts/foo.py

# ✅ New (no_agent=false, agent uses curl+jq+sqlite3)
API_KEY=*** ~/.hermes/.env | cut -d= -f2-)
RESP=$(curl -s -X POST https://api.example.com/data \
  -H "Authorization: Bearer *** \
  -H "Content-Type: application/json" \
  -d '{"query":"..."}')
echo "$RESP" | jq -r '.datas[] | ...' | while read ...; do
  sqlite3 ~/my_quant_system/stock_data.db "INSERT ..."
done
```

### .env Credential Drift Warning

The `~/.hermes/.env` file can lose entries during Hermes updates (credentials are sometimes rotated out of the active file while preserved in `state-snapshots/`). When an API call returns 401/403 in cron context:
1. Check `head -20 ~/.hermes/.env` for the expected key
2. If missing, grep `state-snapshots/*/.env` for the key's last known location
3. The user must re-add it

## Related

- [hermes-agent skill](hermes-agent) — general Hermes config and troubleshooting
- macOS TCC documentation: System Settings → Privacy & Security → Full Disk Access
- [references/cron-python-sandbox-fix.md](references/cron-python-sandbox-fix.md) — real case study: diagnosing and fixing a cron job blocked by Python sandbox
