# Delegation API Key Troubleshooting

## Symptom
`delegate_task` returns 401 `Authentication Fails` even though the main session works fine with the same provider.

## Root Cause
The main session and delegation use **different authentication paths**:

| Component | Auth path | Key source |
|-----------|-----------|------------|
| Main session | Nous gateway (managed) | Gateway's own key or provider config |
| Delegation | Direct API call | `delegation.api_key` in config, or `~/.hermes/.env` env var |

If delegation config has an explicit `api_key` (e.g., `env:DEEPSEEK_API_KEY`) and that env var's key is expired/rotated, delegation fails while main session works.

## Debugging Steps

### 1. Check delegation config
```bash
grep -A10 "^delegation:" ~/.hermes/config.yaml
```

Look for:
- `api_key: env:SOME_VAR` — the env var might be stale
- `api_key: ''` — empty string is NOT equivalent to "inherit from main session"
- `base_url: https://api.deepseek.com/v1` — explicit base_url bypasses gateway

### 2. Test the key directly
```bash
curl -s -w "\nHTTP %{http_code}" https://api.deepseek.com/v1/models \
  -H "Authorization: Bearer $DEEPSEEK_API_KEY"
```
If this returns 401, the key is expired.

### 3. Check .env file
```bash
cat ~/.hermes/.env | grep DEEPSEEK
```
The stale key lives here. Update it with a fresh key from the provider dashboard.

### 4. Fix options

**Option A: Update the env var** (recommended if you have a fresh key)
```bash
# Edit ~/.hermes/.env or ~/.zshrc
export DEEPSEEK_API_KEY=sk-your-new-key
```

**Option B: Remove explicit delegation config** (let it inherit from main)
```bash
hermes config set delegation.api_key ""
hermes config set delegation.base_url ""
```
Note: this ONLY works if the main session uses the same provider AND the provider config has a working key. If main session uses Nous gateway, delegation may still need its own key.

**Option C: Use a different provider for delegation**
```bash
hermes config set delegation.provider openrouter
hermes config set delegation.model openai/gpt-4.1
```

## What does NOT work
- Setting `api_key: ''` (empty string) — Hermes treats this as a literal empty key, not "inherit"
- Setting `api_key: null` — same as empty
- Deleting the line from config.yaml — Hermes re-creates it from defaults

## Verification
```bash
# After fixing, test with a simple delegation
hermes chat -q "delegate a simple task to verify"
```
Then use `delegate_task` with a trivial task to confirm it works.

## Related
- Provider auth docs: https://hermes-agent.nousresearch.com/docs/integrations/providers
- Delegation config: `delegation.*` section in config.yaml
