# Vision provider findings (tested 2026-08-03)

Method: real screenshot PNG (387×48, dense 5-column data table) sent as a base64
data URL to each provider's OpenAI-compatible `/chat/completions`. Errors and
usage fields interpreted as in SKILL.md Step 2.

## Results

| provider | model | image input | latency | notes |
|---|---|---|---|---|
| xiaomi | mimo-v2.5 | ✅ | ~12–18s | transcribed table correctly; content populated with max_tokens≥2000 |
| xiaomi | mimo-v2.5-pro | ❌ 404 | — | "No endpoints found that support image input" |
| deepseek | deepseek-v4-flash / v4-pro | ❌ 400 | — | "unknown variant `image_url`, expected `text`" — text-only API |
| zai | glm-5.2 (full 5.x family) | ❌ 400 | — | no -v/vision models exposed on /models |
| nvidia | meta/llama-3.2-90b-vision-instruct | ✅ | ~30s+ | reads images; Chinese OCR weak on dense screenshots |
| nvidia | nvidia/nemotron-parse | not benchmarked | — | document-parsing focused, promising for OCR |
| nvidia | microsoft/phi-3-vision-128k-instruct | not benchmarked | — | smaller/faster candidate |

## Xiaomi MiMo specifics
- Base: `https://api.xiaomimimo.com/v1`, key `XIAOMI_API_KEY` (platform: platform.xiaomimimo.com)
- Models: `mimo-v2.5`, `mimo-v2.5-asr`, `mimo-v2.5-pro`, `mimo-v2.5-tts`, `mimo-v2.5-tts-voiceclone`, `mimo-v2.5-tts-voicedesign`
- Response has `reasoning_content` (thinking) alongside `content`. With `max_tokens=500` → `finish_reason=length`, `content=""` (answer stuck in reasoning_content). With `max_tokens=2000` → `finish_reason=stop`, content populated.
- `usage.prompt_tokens_details.image_tokens` confirms the image was actually processed (observed 24 tokens).
- User reported mimo-v2.5 also supports video recognition (untested in this session; Hermes has a `video` toolset).

## Hermes integration
- `auxiliary.vision.provider: auto` + empty `model` fails SILENTLY when the user has no `OPENROUTER_API_KEY` / `GOOGLE_API_KEY` — the #1 reason image uploads appear "broken".
- Working config for this user: `auxiliary.vision.provider = xiaomi`, `auxiliary.vision.model = mimo-v2.5`.
- Config change may require a new session / desktop app restart to take effect.
- DeepSeek web chat (chat.deepseek.com) may claim image support — that's the product routing to a separate multimodal backend, NOT the `deepseek-v4-flash` API model (API list: only v4-flash + v4-pro, no VL variant). Always verify against the API.

## MOA relevance
- MOA preset reference models (deepseek-v4-flash / zai glm-5.1 / kimi-k2.6 / minimax-m2.7 / xiaomi mimo-v2.5) are text models; mimo-v2.5 is the only multimodal one. MOA itself cannot see images — pre-convert via auxiliary.vision so the description enters the discussion.
