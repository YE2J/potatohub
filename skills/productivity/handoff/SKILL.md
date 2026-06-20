---
name: handoff
description: Compact the current conversation into a handoff document so another agent (or yourself in a fresh session) can continue the work. Use when the user says "handoff", "create handoff", "/handoff", or "summarize for next session".
version: 1.0.0
author: ported from mattpocock/skills (MIT)
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [handoff, handover, session-transfer, productivity]
---

# Handoff

Write a handoff document summarising the current conversation so a fresh agent (or a new Hermes session) can continue the work.

## Output Location

Save the handoff document to `~/.hermes/handoffs/` with a filename pattern:
`handoff-<YYYY-MM-DD>-<short-topic-slug>.md`

If `~/.hermes/handoffs/` doesn't exist, create it first.

## Required Sections

Every handoff document must include:

### 1. Goal
One sentence. What was the user trying to accomplish?

### 2. Current State
- What's been done so far (don't repeat — summarize)
- What's partially done / in progress
- What's blocked and why

### 3. Key Decisions
Bullet list of decisions made, with brief rationale. Reference ADRs, issue comments, or conversation context.

### 4. Artifacts (links, not copies)
Reference existing artifacts by path or URL — do NOT duplicate:
- PRDs, plans, ADRs → file paths
- GitHub issues/PRs → URLs (e.g. `https://github.com/owner/repo/issues/123`)
- Commits → SHAs or URLs
- Diffs, configs, scripts → file paths

### 5. Environment & Setup
What the next agent needs to know:
- Active virtualenv / node version / docker context
- Required env vars (names only, NOT values — redact secrets)
- Running services (ports, process names)
- Any non-obvious tooling quirks

### 6. Suggested Skills
List Hermes skills the next session should load to be effective:
```yaml
suggested_skills:
  - skill-name-1
  - skill-name-2
```

### 7. Next Steps
Numbered, actionable list. Each item should be completable in one session. Be specific — "Fix the login timeout bug (see #42)" not "Improve auth".

## Rules

- **No duplication.** If something is in a linked artifact, reference it — don't restate it.
- **Redact secrets.** Strip API keys, tokens, passwords, PII. Reference env var names only.
- **Be concise.** The handoff is a map, not a novel. Target 200-500 words.
- **If user passed arguments**, treat them as a description of what the next session should focus on and tailor the doc accordingly.

## Example Structure

```markdown
# Handoff: Fix login timeout — 2026-06-17

## Goal
Fix the 30-second login timeout affecting Safari users.

## Current State
- Root cause identified: missing `keepAlive` on WebSocket in Safari
- Fix implemented in `auth/websocket.ts` but not tested
- CI is green on main

## Key Decisions
- Chose WebSocket keepAlive over HTTP polling — lower latency
- Pinned `ws` to v8.16 to avoid breaking change in v8.17

## Artifacts
- PR: https://github.com/acme/app/pull/142
- ADR: `docs/adr/004-websocket-auth.md`
- Test plan: `docs/test-plans/login-timeout.md`

## Environment
- Node 22, pnpm
- `.env` needs `REDIS_URL`, `JWT_SECRET`
- Redis running locally on :6379

## Suggested Skills
- test-driven-development
- systematic-debugging

## Next Steps
1. Run the integration test suite (`pnpm test:integration`)
2. Deploy to staging and verify Safari
3. If pass, merge #142
```
