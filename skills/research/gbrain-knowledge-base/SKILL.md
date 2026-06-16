---
name: gbrain-knowledge-base
description: "Install, configure, and maintain a GBrain personal knowledge base — an LLM-managed markdown knowledge system with MECE filing, vector search, timeline, and knowledge graphs."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [macos, linux]
metadata:
  hermes:
    tags: [gbrain, knowledge-base, personal-notes, mece, search, embeddings, knowledge-graph, bun]
    homepage: https://github.com/garrytan/gbrain
---

# GBrain Knowledge Base

GBrain is an LLM-managed personal knowledge base by Garry Tan. It stores markdown files in a MECE directory structure, indexes them with vector embeddings, and provides search, timeline tracking, and knowledge graph traversal — all maintained by AI agents.

**Key concepts:**
- **MECE directories** — every piece of knowledge has one home (people/, companies/, concepts/, etc.)
- **Two-layer pages** — compiled truth (above the line, rewritten) + timeline (below the line, append-only)
- **Three DB primitives** — PGLite (local, zero-config) or Supabase pgvector (multi-device)
- **Search modes** — conservative / balanced / tokenmax (25x cost spread)

---

## Installation

### Prerequisites: Bun

```bash
curl -fsSL https://bun.sh/install | bash
export PATH="$HOME/.bun/bin:$PATH"
```

### Install GBrain

```bash
bun install -g github:garrytan/gbrain
gbrain --version   # verify
```

### After Install: Run Migrations

The global install's postinstall hook may be blocked. Run:

```bash
gbrain apply-migrations --yes
```

### Fallback (if global install fails)

```bash
git clone https://github.com/garrytan/gbrain.git ~/gbrain
cd ~/gbrain && bun install && bun link
```

---

## Initialize the Brain

### With Embeddings (recommended — requires API key)

```bash
export OPENAI_API_KEY=sk-...     # or ZEROENTROPY_API_KEY, VOYAGE_API_KEY
gbrain init                       # auto-detects PGLite
```

### Without Embeddings (keyword/FTS search only)

```bash
gbrain init --pglite --no-embedding
# Configure later: gbrain config set embedding_model <id>
# Then: gbrain embed --stale
```

**Pitfall:** `gbrain init` without `--no-embedding` and without any embedding API key set will fail. Use `--no-embedding` to defer, or set a key first.

---

## Search Mode Configuration (Step 3.5 — MUST ASK USER)

`gbrain init` auto-selects a mode but prints a cost matrix. **Always present this to the user before proceeding.**

### Cost Matrix (10K queries/month, search payload only)

| Mode | Haiku 4.5 ($1/M) | Sonnet 4.6 ($3/M) | Opus 4.7 ($5/M) |
|---|---|---|---|
| **conservative** | $40/mo | $120/mo | $200/mo |
| **balanced** | $100/mo | $300/mo | $500/mo |
| **tokenmax** | $200/mo | $600/mo | $1,000/mo |

Scales linearly: ×10 for 100K queries/mo, ÷10 for 1K. 25x corner-to-corner spread.

### Modes

| Mode | Budget | LLM expansion | Chunks | Best for |
|---|---|---|---|---|
| **conservative** | 4K | No | 10 | Cost-sensitive, Haiku |
| **balanced** | 12K | No | 25 | Sonnet sweet spot |
| **tokenmax** | No limit | Yes (with key) | 50 | Frontier models, best quality |

### To set

```bash
gbrain config set search.mode conservative
gbrain config set search.mode balanced
gbrain config set search.mode tokenmax
# Verify:
gbrain search modes
```

**Note:** Without an embedding/LLM API key, `tokenmax` degrades to conservative-like behaviour (no expansion can run).

---

## Create the Content Repository

The recommended MECE directory structure lives outside `~/.gbrain/` — it's a git-tracked markdown repo the agent maintains:

```bash
mkdir -p ~/brain && cd ~/brain && git init
```

### Directory Layout

```
brain/
├── RESOLVER.md     # Decision tree for filing new pages
├── schema.md       # Page conventions (frontmatter, two-layer structure)
├── index.md        # One-line content catalog
├── log.md          # Chronological ingest/update log
├── people/         # One file per human
├── companies/      # One file per organization
├── deals/          # Financial transactions (funding, acquisitions)
├── meetings/       # Specific events with transcripts
├── projects/       # Things being actively built
├── ideas/          # Raw possibilities, not yet committed
├── concepts/       # Mental models, frameworks, teachable ideas
├── writing/        # Written artifacts (essays, posts, notes)
├── programs/       # Major life workstreams
├── org/            # Institutional strategy / operations
├── civic/          # Politics, policy, governance
├── media/          # Public narrative, content, media
├── personal/       # Private notes
├── household/      # Domestic operations
├── hiring/         # Candidate pipelines
├── sources/        # Raw imports (transcripts, exports, scrapes)
├── prompts/        # Reusable LLM prompts
├── inbox/          # Unsorted / temporary captures
├── archive/        # Dead / superseded pages
└── .raw/           # Provenance sidecars
```

### Required Files

**`RESOLVER.md`** — Decision tree the agent walks before creating any page. Start with the ordered yes/no list (see `references/mece-resolver-template.md`).

**`schema.md`** — Page conventions:
- Frontmatter: `slug`, `aliases`, `type`, `created`, `updated`
- **Above the line** (compiled truth, rewritten): executive summary, state fields, open threads, See Also
- **Below the line** (timeline, append-only): dated evidence entries

Each directory needs a **`README.md` resolver** answering what goes here vs what does not.

**Pitfall:** Every directory MUST have a resolver README.md. Without it, agents file things in the wrong place and duplicates accumulate.

---

## Import and Index

### Import markdown files

```bash
cd ~/brain && gbrain import ~/brain/ --no-embed
# Without --no-embed, GBrain tries to embed each page immediately
```

### Generate embeddings (after configuring a key)

```bash
gbrain embed --stale
```

### Verify

```bash
gbrain doctor --json    # comprehensive health check
gbrain stats            # page/chunk/embed/link counts
gbrain query "your question"  # test search
```

---

## Knowledge Graph (Step 4.5)

After importing content, wire the typed-link graph and structured timeline:

```bash
# Preview
gbrain extract links --source db --dry-run | head -20
# Commit
gbrain extract links --source db
# Timeline
gbrain extract timeline --source db
# Verify
gbrain stats   # confirm links > 0
```

**For large brains** (>10K pages): add `--since YYYY-MM-DD` for incremental extraction. Idempotent — safe to re-run.

### Obsidian bare wikilinks

If importing from Obsidian or Notion with `[[note-name]]` (bare wikilinks without path):

```bash
gbrain config set link_resolution.global_basename true
gbrain extract links --source db  # re-run
```

`gbrain doctor` shows a `link_resolution_opportunity` hint with exact count.

---

## Post-Upgrade / Migration

When upgrading GBrain:

```bash
gbrain upgrade          # binary self-update + schema migrations + post-upgrade prompts
gbrain apply-migrations --yes   # manual schema-only (if postinstall blocked)
```

`gbrain init` on an existing brain auto-detects and applies pending migrations.

---

## Pitfalls

### `gbrain skillpack install` is gone

Replaced by `scaffold` in v0.33. Run `migrate-fence` first if upgrading:
```bash
gbrain skillpack migrate-fence
gbrain skillpack scaffold --all --workspace PATH
```

### `gbrain skillpack scaffold --all` needs a git repo root

If installed globally via bun, `scaffold` fails with "could not find gbrain repo root" because there's no git clone. The bundled skills are at:
```
~/.bun/install/global/node_modules/gbrain/skills/
```
They're designed for Claude Code's skill format, not Hermes Agent's SKILL.md format. Use `skill_view()` to inspect them; they won't load directly as Hermes skills.

### No API key → limited functionality

Without any embedding provider key:
- Keyword/FTS search works (`gbrain query "term"`)
- Vector search is unavailable
- `tokenmax` mode degrades to conservative (no LLM expansion)
- `gbrain doctor` reports embedding issues (non-blocking)

### `gbrain import` without `--no-embed`

If no embedding model is configured, `gbrain import` will try and fail to embed. Always use `--no-embed` when importing without an API key.

---

## Verification Checklist

After a fresh install + setup:

- [ ] `gbrain --version` prints a version number
- [ ] `gbrain stats` shows pages > 0
- [ ] `gbrain query "something"` returns results (keyword search)
- [ ] Brain repo is git-initialized and committed
- [ ] Search mode is confirmed with user
- [ ] (If applicable) `gbrain extract links --source db --dry-run` shows links
- [ ] (If applicable) `gbrain doctor` passes all embedding/integrity checks
