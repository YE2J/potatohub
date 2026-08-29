# Daily-Slice Pattern & Consumption Channels (proven 2026-08-24)

Class-level playbook for rescuing a write-only wiki (cron-fed KB that nobody reads).
Proven on the A-share wiki: 每日盘面 page was 2175 lines / 124KB → split into 82
day-slices ≤8KB; wiki went from "write-only archive" to "consumed by morning report
+ Q&A" in one session.

## 1. Write-Only Audit (answer "is the wiki useful?" with data)

```bash
# Action-type distribution in log.md — zero query/lint = write-only
grep -oE '^## \[[0-9-]+\] (ingest|update|query|lint|create|archive|delete)' "$WIKI/log.md" \
  | awk '{print $3}' | sort | uniq -c
# Expect a mix. 56 update + 1 create + 0 query + 0 lint = textbook write-only.

# Downstream consumers — any script/skill that READS the wiki
grep -rl "hermes/wiki" ~/.hermes/scripts/ ~/my_quant_system/ 2>/dev/null
# Empty result = no consumer.
```

Signals: `update` dominates, `query`/`lint` ≈ 0, no consumer files. Root causes:
(1) pages too big to read cheaply → nobody reads; (2) no workflow consumes output.

Fix ORDER matters: shrink pages FIRST, wire a consumer SECOND, keep write cron THIRD.
Never add more write automation to a write-only wiki.

## 2. Daily-Slice Pattern (日切片模式)

- Structure: `concepts/<page>/YYYY-MM-DD.md` + `_latest.md` (verbatim copy of latest day)
- `_latest.md` is the SINGLE fast entry point for consumers; any read ≤ ~8KB regardless
  of page age. 124KB page ≈ 30K tokens per agent read — that's why nobody reads it.
- Every update CREATES/OVERWRITES the day's slice; old slices are immutable history.
  No new data → still create today's slice with "stalled N days" note.
- index.md lists `[[page/_latest]]`, not the bare page.
- **Rewrite the cron prompt** to emit this structure — otherwise next cron run re-appends
  to the old single file and undoes the split.
- Migration: `scripts/wiki_split_daily.py` (splits pages whose sections start with
  `## YYYY-MM-DD`; archives originals to `_archive/`). Back up wiki dir first.

## 3. Consumption Channels (pick ≥1; script consumer is the cheapest to wire)

1. **Batch/script consumer** — no_agent cron output reads `_latest.md` for dimensions its
   own DB queries lack (morning report gained valuation/L2/L3/两融 — 290 chars, all
   previously missing). Rules: pure read-only addition; never rewire the script's own
   data source; register the new block in the script's truncation priority list so it
   gets dropped first under the char limit.
2. **Agent Q&A first-check** — add step 0 to the data-query skill's execution flow:
   "for overview questions read `_latest.md` first; answer from wiki when it covers the
   question; fall back to live scripts when it doesn't or data is stale." Mark answers
   "来源: wiki 每日整理" so the user knows provenance.
3. **Index pointers** — index.md entries point at `_latest.md` so orientation reads land
   on the fresh slice instantly.

## Session specifics (A-share wiki, 2026-08-24)

- Wiki lives at `~/.hermes/wiki/` (NOT the llm-wiki default `~/wiki`) — check
  `~/.hermes/wiki` when the default path looks empty.
- Split: 每日盘面 27 days, 资金流追踪 26 days, 估值动态 26 days → 82 files + 3 `_latest.md`.
- Cron `82d135d6a369` (Wiki 增量整理, 03:30) prompt rewritten to daily-slice mode.
- Morning report `daily_morning_report_v7.py` gained `report_wiki_latest()` — reads
  `~/.hermes/wiki/concepts/估值动态/_latest.md`, extracts L2/L3/两融/估值 table rows,
  emits "📚 Wiki 估值/L2/L3" block in Tue–Sat full editions only; truncation priority 7.
- `a-share-data` skill execution flow gained step 0 (wiki-first for overview questions).
- Script: `~/.hermes/scripts/wiki_split_daily.py` (also mirrored under this skill).
