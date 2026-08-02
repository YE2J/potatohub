# pyenv Python as Sandbox Workaround

When Hermes venv's Python has incompatible dependency trees (e.g. urllib3 requires Python 3.10+ features but Hermes runs 3.11 with a stale urllib3), pyenv-managed Python is a zero-setup alternative to installing standalone Python in `~/.hermes/`.

## The Pattern

```bash
PYTHON=~/.pyenv/versions/3.11.11/bin/python
$PYTHON scripts/foo.py
```

## When To Use

- The script imports packages that aren't in Hermes venv (requests, pandas, etc.)
- Hermes venv has incompatible pinned versions (e.g. TypeError: `unsupported operand type(s) for |: 'type' and 'type'` from urllib3 + Python 3.11 mismatch)
- The script lives in the user's `~/my_quant_system/` project, which has its own venv or environment
- You need `requests`, `sqlite3`, or standard library modules in a clean version

## Example Error

```
TypeError: unsupported operand type(s) for |: 'type' and 'type'
  File ".../urllib3/_base_connection.py", line 10
    bytes, typing.IO[typing.Any], typing.Iterable[bytes | str], str
```

This happens when urllib3 (installed in Hermes venv) uses Python 3.10+ `X | Y` union syntax, but the running interpreter or the package resolution chain breaks. Using pyenv's Python sidesteps the Hermes venv entirely.

## Finding the Right Python

```bash
# List available pyenv versions
ls ~/.pyenv/versions/

# Check if a specific version works
~/.pyenv/versions/3.11.11/bin/python -c "import requests; print('OK')"

# Or check the project's own venv
~/my_quant_system/.venv/bin/python -c "import requests; print('OK')"
```

## Integration with Scripts

In scripts or cron jobs, pass the python path explicitly:

```bash
# In a shell script
PY=~/.pyenv/versions/3.11.11/bin/python
"$PY" "$PROJECT_DIR/scripts/import_financial_api.py" --table hot_stock_daily

# Or set as default for the session
alias py3="~/.pyenv/versions/3.11.11/bin/python"
```

## Limitations

- pyenv must already be installed and have the target version compiled — this is NOT a fix for a system without pyenv
- The pyenv Python's site-packages are separate from Hermes venv — any packages the script needs must be installed in the pyenv environment
- Does NOT work inside `no_agent=true` cron jobs (TCC blocks all user-installed Python binaries)
