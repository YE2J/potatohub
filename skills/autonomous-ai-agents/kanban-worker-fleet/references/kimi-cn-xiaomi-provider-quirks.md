# Kimi CN & Xiaomi MiMo Provider Quirks

## Kimi CN (`kimi-coding-cn`)

**Endpoint:** `https://api.moonshot.cn/v1`  
**Env var:** `KIMI_CN_API_KEY`  
**Key format:** `sk-...`

### Available models (2026-07-12)
- `kimi-k2.7-code` ★ recommended (newest coding model)
- `kimi-k2.6` — general multimodal (discontinued May 2026, still works)
- `kimi-k2.5`
- `moonshot-v1-auto`
- `moonshot-v1-8k` / `moonshot-v1-32k` / `moonshot-v1-128k`
- `moonshot-v1-8k-vision-preview` / `moonshot-v1-32k-vision-preview` / `moonshot-v1-128k-vision-preview`
- `kimi-k2.7-code-highspeed`

### `hermes status` doesn't show it
The default `hermes status` checks for `KIMI_API_KEY` (international), not `KIMI_CN_API_KEY`. This does NOT mean the key is missing — the CN endpoint just uses a different env var name.

### Known instability
Kimi K2.7-code has ~2/9 crash rate (protocol violation — exits without calling `kanban_complete`). Add `fallback_providers` to worker-kimi's config.yaml as mitigation.

---

## Xiaomi MiMo (`xiaomi`)

**Endpoint:** `https://api.xiaomimimo.com/v1`  
**Env var:** `XIAOMI_API_KEY`  
- `mimo-v2.5`, `mimo-v2-omni` (vision)

### `supports_health_check=False`
The plugin declares `supports_health_check=False` because `/v1/models` returns 401 even with a valid key. This means:
- `hermes status` → does NOT show Xiaomi in the provider list
- `hermes auth list` → does NOT show it
- **The key CAN still be valid** — test via direct curl to `/v1/chat/completions`

### Fast inference
MiMo v2.5-pro is noticeably faster than other workers (~30-60s per task vs GLM's ~68s or MiniMax's ~80-118s).

### Use with Kanban
Create profile:
```bash
hermes profile create worker-xiaomi --clone-from default
hermes config set model.provider xiaomi --profile worker-xiaomi
hermes config set model.default mimo-v2.5 --profile worker-xiaomi
hermes config set model.base_url '' --profile worker-xiaomi
```
