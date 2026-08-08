---
name: hermes-vision-config
description: "Set up image input for Hermes on a text-only main model."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [macos, linux, windows]
metadata:
  hermes:
    tags: [hermes, vision, auxiliary, multimodal, image-analysis, provider-probing]
---

# Hermes Vision Config (auxiliary.vision)

When the main model is text-only (e.g. deepseek-v4-flash), uploaded images can't be seen directly. Hermes solves this with an auxiliary vision model (`auxiliary.vision` config): image → text description → main model reasons over the text. This skill covers setting that up and verifying which provider/model can actually see images.

## Triggers
- 用户上传图片但主模型读不了（"扫码 / 识图 / 读图 / 识别这张图"）
- "哪个模型能识别图片，速度最快" / "Which model can recognize this image?"
- Configuring or debugging `auxiliary.vision`
- Choosing a multimodal model among the user's API keys

## How the routing works
1. User uploads image → Hermes sends it to `auxiliary.vision.provider/model`
2. Vision model returns a text description
3. Description is injected into context → main (text-only) model reasons over it

## Step 1 — Check current config
```bash
grep -A6 "auxiliary:" ~/.hermes/config.yaml
```
- `provider: auto` + empty `model` means "find a backend" — it fails SILENTLY when the user has no `OPENROUTER_API_KEY` / `GOOGLE_API_KEY`. This is the #1 reason uploads fail.
- Fix: set an explicit provider + model (Step 3).

## Step 2 — Probe which provider accepts image input (never guess)
Send a real image (base64 data URL) to each candidate via OpenAI-compatible `chat/completions` and interpret the response:
- `HTTP 400 "unknown variant image_url, expected text"` → model is TEXT-ONLY
- `HTTP 404 "No endpoints found that support image input"` → model has no vision endpoint
- `HTTP 200` + `usage.prompt_tokens_details.image_tokens > 0` → vision works
- `200` but `content` empty + `finish_reason=length` → reasoning model ate the token budget; raise `max_tokens` (≥2000) and re-check `content`

Use `scripts/probe_vision_models.py <image.png> [provider] [model]` — it automates all of the above and prints latency + extracted content.

Provider base URLs / key env vars for manual probes:

| provider | base_url | key env |
|---|---|---|
| xiaomi | https://api.xiaomimimo.com/v1 | XIAOMI_API_KEY |
| deepseek | https://api.deepseek.com/v1 | DEEPSEEK_API_KEY |
| zai | https://api.z.ai/api/paas/v4 | ZAI_API_KEY (or GLM_API_KEY) |
| nvidia | https://integrate.api.nvidia.com/v1 | NVIDIA_API_KEY |

See `references/vision-provider-findings.md` for tested per-provider results and quirks.

## Step 3 — Configure
```bash
hermes config set auxiliary.vision.provider <provider>
hermes config set auxiliary.vision.model <model>
```
- Config change may need a new session / desktop app restart to take effect.
- Use the exact model id — verify against the provider's `/v1/models` first (flagship ≠ vision-capable).

## Pitfalls
- **max_tokens too low** → MiMo-style reasoning models put the final answer in `content` only when enough budget remains; a low budget leaves `content` empty with the answer trapped in `reasoning_content` (finish_reason=length). Always retry with max_tokens≥2000 before concluding the model can't answer.
- **mimo-v2.5 vs -pro**: on Xiaomi MiMo, `mimo-v2.5` accepts images; `mimo-v2.5-pro` returns 404 (no image endpoint). Check the exact model, not the flagship.
- **PIL broken in Hermes venv** (`cannot import name '_imaging'`): generate test images in a separate venv (`python3 -m venv /tmp/vt_venv && /tmp/vt_venv/bin/pip install pillow`), never the Hermes venv.
- **terminal lifecycle guard crash** ("embedded null byte" when a command references a `.py` script under /tmp): use inline `python3 -c '...'` instead of running a script file.
- **Default PIL font can't render CJK**: Chinese test text renders as blank boxes → OCR looks broken when it isn't. Load a real font (e.g. `/System/Library/Fonts/PingFang.ttc`).
- **MOA is text-only**: even with a multimodal reference model (mimo-v2.5), MOA models receive text. Route the image through auxiliary.vision FIRST so the description can enter any downstream flow (MOA/Kanban).
- **Web-product claims ≠ API capability**: e.g. chat.deepseek.com saying "v4-flash supports images" refers to the product's separate multimodal backend, not the deepseek API model. Verify against the API before believing it.

## Files
- `scripts/probe_vision_models.py` — reusable vision-capability probe
- `references/vision-provider-findings.md` — per-provider tested results + quirks
