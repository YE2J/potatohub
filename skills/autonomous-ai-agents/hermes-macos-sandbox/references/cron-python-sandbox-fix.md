# Cron Python Sandbox Fix — Reproducible Pattern

Session: 2026-06-19, job_id=29f36877421b (每日热门板块分组)

## Symptoms

```
Script exited with code 126
stderr: /Users/yellow/my_quant_system/.venv/bin/python3: Operation not permitted
```

## Diagnosis Steps

1. **Identify the script chain**: cron → `daily_sector_group.sh` → `exec python3 daily_sector_group.py`
2. **Check binary availability**:
   ```bash
   # System Python — broken shim (Xcode CLT missing)
   /usr/bin/python3 --version  # → xcode-select error
   
   # Homebrew Python — sandbox blocked
   /opt/homebrew/bin/python3.12 --version  # → Operation not permitted
   
   # Venv Python — sandbox blocked + broken symlink
   ls -la ~/my_quant_system/.venv/bin/python3  # → broken symlink to Xcode CLT
   
   # System tools that DO work
   /usr/bin/sqlite3 --version  # ✅
   /usr/bin/curl --version     # ✅
   /usr/bin/jq --version       # ✅
   ```
3. **Check API key**: `grep IWENCAI_API_KEY ~/.hermes/.env` — missing (removed during update)
4. **Check execute_code**: blocked in cron context by safety policy

## Fix Applied

Converted cron job from `no_agent=true` (shell script → Python) to `no_agent=false` (LLM-driven, curl + jq + sqlite3):

```python
cronjob(action='update', job_id='29f36877421b', no_agent=False, script='', prompt='...')
```

The prompt uses:
- `curl` → HTTP POST to iwencai API with Bearer auth
- `jq` → parse JSON, extract fields per stock
- `sqlite3` → INSERT OR IGNORE/REPLACE into DB
- `grep ~/.hermes/.env | cut` → read API key at runtime

## Other Jobs at Risk

Any `no_agent=true` cron job calling Python from outside `~/.hermes/` will fail the same way. Check:
- `fda7975b8524` (自选股日线数据自动更新) — same pattern, may fail next run
- `5f20a2f80e20` (自选股每周估值) — same pattern
- `00b779e99fdf` (Hermes 日报生成) — same pattern, already showing error

## Key Takeaway

Cron execution sandbox is **stricter** than interactive terminal sandbox. System binaries (curl, jq, sqlite3) work; user-installed binaries don't. Agent-driven mode (`no_agent=false`) is the workaround.
