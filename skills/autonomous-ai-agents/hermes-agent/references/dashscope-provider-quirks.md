# DashScope / Qwen Provider Quirks

## China vs International Endpoint

DashScope API keys come in two flavors:

| Endpoint | URL | Key prefix |
|----------|-----|------------|
| 国际 (International) | `https://dashscope-intl.aliyuncs.com/compatible-mode/v1` | `sk-` |
| 中国 (China) | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `sk-ws-` (workspace) |

Hermes's built-in `alibaba` / `dashscope` provider **hardcodes the international endpoint**. If the user has a China-market API key (common for mainland users), it will fail with `HTTP 401: Incorrect API key provided` even though the key is valid.

### The Fix

```bash
hermes config set model.provider alibaba --profile <profile>
hermes config set model.base_url "https://dashscope.aliyuncs.com/compatible-mode/v1" --profile <profile>
# api_key must be set directly in config.yaml (env:DASHSCOPE_API_KEY won't resolve properly with custom base_url)
```

Then set `model.api_key` to the raw key value in `config.yaml`:
```yaml
model:
  provider: alibaba
  base_url: https://dashscope.aliyuncs.com/compatible-mode/v1
  api_key: sk-ws-H.xxxx  # put raw key here, not env:XXX
```

### What didn't work
- `provider: dashscope` — same as alibaba, hardcodes international endpoint
- `provider: custom:dashscope-cn` — unknown provider error unless `providers:` section is defined
- `providers.dashscope-cn.api_key_env: DASHSCOPE_API_KEY` — env var resolution doesn't work for custom providers
- `model.api_key: env:DASHSCOPE_API_KEY` — doesn't resolve with alibaba provider either

### Arrears / 欠费
If the DashScope account runs out of quota, ALL models return `HTTP 400 Arrearage`. Even free-tier models like `qwen-plus` stop working. The fix is to top up at https://dashscope.aliyun.com/.

### Available models (China endpoint, as of 2026-06)
- `qwen3.7-max` — flagship (requires paid account)
- `qwen3.7-plus` — latest plus
- `qwen-plus` — stable plus
- `deepseek-v4-pro`, `deepseek-v4-flash` — via DashScope mirror
- `glm-5`, `glm-5.1` — Zhipu models via mirror
- `kimi-k2.6`, `kimi-k2.7-code` — Moonshot models via mirror
