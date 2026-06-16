---
name: terminal-secrets
description: Handle API keys, tokens, and credentials in terminal commands and config files. Hermes security scanner can corrupt exported env vars — use config files instead.
---

# Terminal Secrets Management

Hermes security scanner masks sensitive-looking strings (API keys, tokens) in the terminal tool. An `export` command with a real key **may execute with the literal value `***`** instead of your key.

## The Problem

```bash
# What you type:
export ZEROENTROPY_API_KEY="ze_abc123..."
# What actually executes:
export ZEROENTROPY_API_KEY="***"
# The env var is now literally "***" (length 3)
```

**How to detect it:**
```bash
echo "Length: ${#ZEROENTROPY_API_KEY}"   # If 3 → value is "***"
echo "Prefix: ${ZEROENTROPY_API_KEY:0:5}" # If "***..." → broken
```

## The Fix

**Never `export KEY=value` in a Hermes terminal command.** Write the key to a file instead.

### Option A: Config file (preferred)

Use `write_file` or `patch` (Hermes doesn't mask file content):

```bash
# via patch tool — safe
patch path=~/.myapp/config.json old_string="\"some_field\": \"old_val\"" new_string="\"some_field\": \"real_key\""

# via write_file — safe
write_file path=~/.myapp/.env content="MY_KEY=real_key"
```

### Option B: Shell profile

```bash
echo 'export MY_KEY="real_value"' >> ~/.zshrc   # Safe — file write
source ~/.zshrc                                   # Safe — sourced, not handed to terminal as a literal
```

The shell profile line is safe because the value is written to the file first. When `source` reads from the file, the shell gets the real value — Hermes only scrubs inline `export` commands typed into the terminal.

### Option C: curl headers (usually safe)

Bearer tokens in `-H "Authorization: Bearer sk-..."` are typically NOT scrubbed — Hermes treats them as header values, not env assignments.

## Pitfalls

- **`export KEY=***` sets `KEY` to literal `***`** — always verify key length after export
- **Config files survive terminal sessions** — env vars are lost when session resets
- **Some tools read only env vars** — for those you must use the shell profile approach (Option B)
- **`gbrain config set` writes to DB plane, not file plane** — gbrain's embed pipeline ignores it. Write `zeroentropy_api_key` directly to `~/.gbrain/config.json` instead

## Verification

After setting a secret, verify with a live API call:

```bash
curl -s -w "\nHTTP: %{http_code}" \
  -X POST "https://api.someprovider.com/v1/models/embed" \
  -H "Authorization: Bearer $MY_KEY" \
  -H "Content-Type: application/json" \
  -d '{"input":"test","model":"some-model"}'
```

A 200 response confirms the key works. A 401/403 means the key is missing or wrong.
