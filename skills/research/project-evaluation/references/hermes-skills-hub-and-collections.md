# Hermes Skills Hub & GitHub Skill Collections — Session Notes (2026-08)

Verified during the "agentic-awesome-skills 适不适合我" session. Records what actually worked and the exact observed behavior.

## Network probe results (2026-08, this machine)

| Path | Result |
|------|--------|
| `hermes skills search <kw>` (Hub CLI) | ✅ Works — 88K skills loaded, page 1/4400 |
| `hermes skills browse` | ✅ Works (87994 skills, 111 official optional) |
| web_search / web_extract (Nous Portal) | ❌ SSL UNEXPECTED_EOF — OAuth device_code needs refresh via `hermes auth` (user-interactive, can't be done by agent) |
| GitHub Search API / raw.githubusercontent | ❌ HTTP 000 connection reset (network env) |
| gh CLI | ❌ not installed |

Takeaway: Hub CLI is the only reliable discovery path in this environment. It is NOT a proxy for arbitrary GitHub repos — only for skill-shaped assets that skills.sh/clawhub have indexed.

## Hub search behaviors observed

- `hermes skills search quant` → 25 results, including `clawhub` source entries and `skills-sh/<owner>/<repo>/<skill>` identifiers (GitHub repos indexed by skills.sh, e.g. `sickn33/antigravity-awesome-skills`).
- `hermes skills search awesome` → 25 results (aradotso collections, `awesome-claude-skills` from clawhub, etc.).
- `hermes skills search agentic` → 25 results (no exact "agentic-awesome-skills").
- `hermes skills search "agentic-awesome"` and `"awesome-agentic"` → **0 results** → repo not indexed → too new/long-tail.
- Hub output columns: Name | Description | Source (official/clawhub/skills.sh) | Trust (official/community) | Identifier.

## Decision rules used

1. Hub search first for any skill-shaped question — partial repo names work as keywords.
2. Exact-name 0 hits = not indexed; then decide whether to fetch by another path (user-paste README, VPN, Portal refresh) or skip.
3. For collection repos, don't install — extract ≤5 candidates via scenario-driven `inspect`.
4. Batch install / tap-add without inspect = index pollution. Never.

## How the user reacted

- User is interested in the skill-ecosystem question, not in bulk adoption. The valuable deliverable is the suitability analysis (定位/重复度/兼容/用法), not installing.
- User's pipeline (A-share quant, THS/TDX data, WeChat morning report) is vertical — collections cover it ≈ 0%. User's own skills are the primary asset.
