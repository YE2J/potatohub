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

2. **Do NOT use `python3.11` if `python3.12` is available.** On macOS 26.2 both are broken, but 3.12 with `uv` is the tested working path.

3. **`uv`'s `--python` flag downloads a CPython build.** First run may take 10–30 seconds for the download. Subsequent runs are cached.

4. **PEP 668 compliance.** `uv` creates isolated venvs by default — no `--break-system-packages` needed.

## References

- `references/macos26-python-failures.md` — exact error transcripts from the broken Homebrew CPython session
