---
name: python-toolchain-macos
description: Python venv/pip/bootstrap fixes for macOS, especially when Homebrew CPython is broken. Use when venv creation fails, pip is missing, or `python3 -m ensurepip` errors out.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [python, macos, venv, pip, homebrew, uv]
    related_skills: [hermes-agent]
---

# Python Toolchain — macOS Bootstrap

## Overview

Homebrew-installed CPython on macOS (especially Sequoia 26.x) is **frequently broken** when it comes to venv/pip. Both `python3.11` and `python3.12` can fail with:

- `ensurepip` returning non-zero exit status
- `pyexpat` ImportError due to `_XML_SetAllocTrackerActivationThreshold` symbol mismatch with system `/usr/lib/libexpat.1.dylib`

**The reliable escape hatch is `uv`** (from Homebrew).

## When to Use

- Any time `python3 -m venv venv` fails on macOS
- When `pip install` errors out inside a freshly created venv
- When `ensurepip` or `pyexpat` errors appear
- First time setting up a Python project on macOS — skip `venv`, use `uv` proactively

## Procedure

### Step 1: Install uv (one-time)

```shell
brew install uv
```

### Step 2: Create venv with uv

```shell
cd <project>
uv venv --python 3.12         # or 3.11, 3.13 — uv downloads a working CPython
source .venv/bin/activate
```

uv downloads a fresh, working CPython build — it does **not** reuse the broken Homebrew one.

### Step 3: Install packages

```shell
uv pip install -e .             # for editable installs
uv pip install <package>        # for individual packages
```

## Verification

```shell
python -c "import sys; print(sys.version)"
pip --version
```

## Pitfalls

1. **Do NOT try `python3.X -m venv --without-pip venv` then `curl | python` to install pip.** The underlying CPython in Homebrew is broken at the binary level (pyexpat symbols), not just missing pip. `uv` downloads an entirely separate working CPython.

2. **macOS system Python 3.9.6 is a viable fallback** when `uv` is not installed. `/usr/bin/python3` ships with macOS and is guaranteed compatible. Limitation: only Python 3.9, some modern packages may need >=3.10.

3. **Do NOT use Homebrew Python 3.11.15_3 on macOS 26.2.** Confirmed broken: `python3.11 -c "import xml.parsers.expat"` fails with `Symbol not found: _XML_SetAllocTrackerActivationThreshold`. The system `/usr/lib/libexpat.1.dylib` lacks this symbol.

4. **`uv`'s `--python` flag downloads a CPython build.** First run may take 10–30 seconds for the download. Subsequent runs are cached.

5. **PEP 668 compliance.** `uv` creates isolated venvs by default — no `--break-system-packages` needed.

6. **`~/.local/bin/python3.11` as pyenv sandbox bypass.** When Homebrew's pyenv python fails with `Library not loaded: /opt/homebrew/opt/gettext/lib/libintl.8.dylib (blocked by sandbox)`, try `~/.local/bin/python3.11`. This is an independently-installed CPython (from python.org installer or `uv`) that does not depend on Homebrew's gettext. It bypasses the libintl sandbox lock. **Check first**: `ls -la ~/.local/bin/python3.11 && ~/.local/bin/python3.11 --version`. Add to cron prompts as a fallback Python path.

7. **In cron prompts, prefer `~/.local/bin/python3.11` over `~/.pyenv/versions/3.11.11/bin/python3.11` on macOS 26.x.** The pyenv path inherits Homebrew's broken gettext linkage. The `~/.local/bin/` path is a standalone build and works reliably in cron/launchd sandbox context.

8. **Secondary venv sys.path pollution when called from Hermes.** When Hermes (running py3.11) spawns a terminal command using **any** secondary venv (project `.venv`, `venv_stock`, etc.) that runs a different Python version, the Hermes agent's py3.11 site-packages leak onto `sys.path` via the global `PYTHONPATH` environment variable. C-extension modules (numpy, pandas, etc.) compiled for py3.11 fail when loaded by a py3.9 interpreter:

   ```
   ModuleNotFoundError: No module named 'numpy._core._multiarray_umath'
   ```

   **Detection:** `echo $PYTHONPATH` shows `<hermes-venv>/lib/python3.11/site-packages`.  
   Also visible: `python -c "import sys; print(sys.path)"` shows the Hermes venv path before the secondary venv's own site-packages.

   **Preferred Fix — clear PYTHONPATH entirely:**
   ```shell
   PYTHONPATH="" /path/to/venv/bin/python script.py
   ```
   This strips all Hermes-injected paths, forcing Python to use only the secondary venv's own site-packages and system stdlib. Works for any project venv regardless of path.

   **Pro tip:** Create a shell alias so you don't have to type `PYTHONPATH=""` every time:
   ```shell
   alias bp="PYTHONPATH=\"\" /Users/yellow/my_quant_system/.venv/bin/python"
   ```

## References

- `references/macos26-python-failures.md` — exact error transcripts from the broken Homebrew CPython session
