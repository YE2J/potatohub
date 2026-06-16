# ZeroEntropy + GBrain: API Key Configuration

## Key Facts
- ZeroEntropy API endpoint: `POST https://api.zeroentropy.dev/v1/models/embed`
  - NOT `/v1/embeddings` (that returns 404)
  - NOT `api.zeroentropy.ai` (use `api.zeroentropy.dev`)
- Required fields: `model`, `input_type` (`"query"` or `"document"`), `input`
- Valid dimensions for zembed-1: [2560, 1280, 640, 320, 160, 80, 40]
- Pricing: $0.05/1M tokens
- Auth: `Authorization: Bearer <key>` header

## GBrain Configuration

### The Two Config Planes (critical)

GBrain has two config planes:

| Plane | Storage | How to write | Embed pipeline reads? |
|-------|---------|-------------|----------------------|
| **File plane** | `~/.gbrain/config.json` | Edit JSON directly | ✅ Yes |
| **DB plane** | PGLite config table | `gbrain config set` | ❌ No (silent no-op) |

**Always put `zeroentropy_api_key` in the file plane, never via `gbrain config set`.**

### Correct init with ZeroEntropy

```bash
# Fresh init with embedding model
gbrain init --pglite --embedding-model zeroentropyai:zembed-1

# Add key to file plane
# Edit ~/.gbrain/config.json to add:
# "zeroentropy_api_key": "ze_..."

# Import and embed
gbrain import ~/brain/
gbrain embed --stale
```

### If you accidentally initialized with --no-embedding

The `embedding_disabled: true` flag persists in `config.json` across reinit calls. Full wipe-and-reinit:

```bash
rm -rf ~/.gbrain/brain.pglite ~/.gbrain/config.json
gbrain init --pglite --embedding-model zeroentropyai:zembed-1
gbrain import ~/brain/
gbrain embed --stale
```

### Dimension mismatch recovery

If `gbrain doctor` reports a dimension mismatch (e.g. schema has vector(2560) but zembed-1 expects 1280):

```bash
rm -f ~/.gbrain/brain.pglite.bak
gbrain reinit-pglite --embedding-model zeroentropyai:zembed-1 --embedding-dimensions 2560 --yes
```

### Verification

```bash
# Direct API test (env var works here because auth header format isn't masked)
curl -s -X POST "https://api.zeroentropy.dev/v1/models/embed" \
  -H "Authorization: Bearer ze_..." \
  -H "Content-Type: application/json" \
  -d '{"model":"zembed-1","input_type":"query","input":"test","dimensions":2560}'

# Gbrain verification
gbrain doctor | grep embedding_provider
gbrain stats   # Should show Embedded: N > 0
gbrain query "test"  # Semantic search should return results with scores
```
