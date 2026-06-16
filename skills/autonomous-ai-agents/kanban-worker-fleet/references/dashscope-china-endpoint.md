# DashScope China Endpoint Fix

## Problem

DashScope API key (format `sk-ws-H.xxxxx`) works perfectly with curl against `dashscope.aliyuncs.com` but Hermes `alibaba`/`dashscope` providers hit `dashscope-intl.aliyuncs.com` and return 401 "Incorrect API key provided."

## Root Cause

Hermes' built-in `alibaba` and `dashscope` providers hardcode the international endpoint. China-market DashScope keys only work against `dashscope.aliyuncs.com`.

## Diagnostic

```bash
# Test key against China endpoint directly
curl -s -w "\nHTTP_CODE:%{http_code}" \
  "https://dashscope.aliyuncs.com/compatible-mode/v1/models" \
  -H "Authorization: Bearer $DASHSCOPE_API_KEY"

# If this returns 200, the key is valid — it's an endpoint routing problem.
```

## Fix

```bash
# 1. Use 'alibaba' provider (not 'dashscope' or 'custom:dashscope-cn')
hermes config set model.provider alibaba --profile worker-qwen

# 2. Override base_url to China endpoint
hermes config set model.base_url "https://dashscope.aliyuncs.com/compatible-mode/v1" --profile worker-qwen

# 3. Set api_key directly (env var resolution may fail with alibaba provider)
#    Method A: hermes config set (may redact long values)
hermes config set model.api_key "sk-ws-H.xxxxx" --profile worker-qwen

#    Method B: execute_code to inject key without redaction
#    Read from .env and write to config.yaml programmatically
```

## What Does NOT Work

- `provider: dashscope` — hardcodes international endpoint, `base_url` override ignored
- `provider: alibaba-coding-plan` — also hardcodes international endpoint  
- `provider: custom:dashscope-cn` — unrecognized without `providers.*` config, and even with it, api_key resolution is unreliable
- `model.api_key: env:DASHSCOPE_API_KEY` — env var resolution broken in alibaba provider context
- Setting `DASHSCOPE_API_KEY` in shell before running hermes — provider ignores it

## Key Format Clue

## Arrears (Account Overdue)

If you get HTTP 400 "Access denied, please make sure your account is in good standing" with error code `Arrearage`, even for previously-working models like `qwen-plus`:

- **All DashScope models are blocked** — the entire account is in arrears
- Top up at https://dashscope.aliyun.com/ (阿里云百炼控制台)
- After topping up, `qwen3.7-max` should work immediately

## Model Name Quick Reference

| Model | Status | Notes |
|-------|--------|-------|
| `qwen3.7-max` | ✅ Best | Latest flagship, large context |
| `qwen3.7-plus` | ✅ | Mid-tier, needs paid account |
| `qwen-plus` | ✅ Free tier | Works without payment as of 2026-06 |
| `qwen-plus-latest` | ⚠️ Needs payment | Aliased version needs active payment |
| `qwen-max` | ❌ Too small | ~32K context, below Hermes 64K minimum |
| `qwen-flash` | ✅ | Budget option |

Diagnose available models directly:
```bash
curl -s "https://dashscope.aliyuncs.com/compatible-mode/v1/models" \
  -H "Authorization: Bearer $DASHSCOPE_API_KEY" | python3 -c "import sys,json; [print(m['id']) for m in json.load(sys.stdin)['data'] if 'qwen' in m['id'].lower()]"
```

## Key Format Clue

China-market keys have a `H.` segment: `sk-ws-H.REYRPEY.xxxxx`
International keys lack the `H`: `sk-xxxxxxxxxxxx`
