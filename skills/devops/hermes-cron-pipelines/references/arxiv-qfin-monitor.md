# arXiv q-fin Monitor: Silent-Miss Diagnosis & API Lessons (2026-09)

User's production arXiv paper-monitor cron (`6921de23673c`, script `~/.hermes/scripts/arxiv_qfin_daily.py`) silently missed ~11 days of papers. Below: the diagnostic pattern, the falsified hypothesis, the real root cause, and the fix — all verified against live behavior.

## Diagnostic pattern: "source healthy but 0 fresh in window"

A mechanical-script cron logged, for 11 consecutive runs:
`API 返回 200 条, 24h 窗口内 0 条` (returned 200 entries, 0 inside 24h window) — while ~1-12 q-fin papers/day were actually being published.

**Interpretation**: when a poll returns plenty of entries but repeatedly 0 *fresh* ones while the source is clearly publishing, suspect the FILTER/WINDOW logic — not the network, not the source. Check in this order:
1. Run-time vs source announcement time-of-day (see below) — the classic cause.
2. Does the query sort order / page size actually surface the newest items?
3. Falsify hypotheses with a LIVE probe of the same query before patching — do not trust a failure report's guessed root cause.

### Falsified hypothesis (lesson: verify before patching)

The incident report claimed "top-200 list crowded out by revised (v2+) versions → new announcements pushed out of page". A live probe of the same query FALSIFIED this: revised entries were only 20/200 = 10%, and the top-200 spanned a full month (2026-08-02→09-03). The report's preferred fix (based on the wrong cause) would not have fixed it.

## Real root cause: poll time vs arXiv announcement time

- arXiv announces new submissions around **20:00 UTC** (~04:00 Beijing) daily; entries become API-queryable only after announcement.
- `published` field ≈ submission timestamp (can precede announcement by hours).
- The script ran 03:10 CST = **19:10 UTC — ~50 min BEFORE the announcement**. Its 24h `published` window edge therefore excluded that day's batch. Evidence: same script with a 72h window (run 08-23 22:50) caught 2 papers; every 24h run since caught 0.
- A 09-04 `Connection reset by peer` then caused exit 1 (single-shot fetch, no retry) — the network failure was a red herring on top of the logic bug.

## Fix pattern (rewrite)

1. **Source-side date-range query** instead of top-N + local window math:
   `search_query=cat:q-fin.* AND submittedDate:[202608200000 TO 202609050000]` (format `YYYYMMDDHHMM` UTC; combine with `AND`; upper bound now+1d for clock skew).
2. **Poll after the announcement hour** (04:30+ Beijing) — or accept weekly granularity where the range tolerance covers it.
3. **Backoff retries** (60s/300s/900s) on network-level errors only; HTTP status errors still fail fast.
4. Configurable window via env (`ARXIV_SINCE_DAYS` default 7, `ARXIV_SINCE_DATE=YYYYMMDDHHMM` for backfill); dedupe by archive-dir existence.

## Pipeline ops facts

- Mechanical layer: `~/.hermes/scripts/arxiv_qfin_daily.py` → downloads PDF → markdown (prefer arXiv HTML via markitdown, fallback PDF) → `~/paper_library/q-fin/<arxiv_id>/{paper.pdf,paper.md,meta.json}` → rebuilds `INDEX.md`. Stdout contract `NEW_PAPERS=N` + `id|title|cats|md_path` rows; empty = silent.
- Agent layer (cron prompt): grades vs `~/paper_library/q-fin/TRIAGE.md` five-dimension scorecard (A=build skill / B=enhance skill / C=concept card / D=archive); appends rows to §2 ledger; reports A/B only; suggestions never auto-executed.
- Cron now weekly **Saturday 02:00 CST** (`0 2 * * 6`), deliver=all. Logs: `~/.logs/arxiv_qfin.log`.
- Backfill run `ARXIV_SINCE_DATE=202608200000` fetched 76 papers in ~2 min (08-20→09-03).

## Batch grading (76+ papers) playbook

- Split by published date into two halves → delegate to two parallel workers, each with an explicit ID list + TRIAGE rules + user context (A-share quant relevance lens) in the prompt.
- Two-stage token filter: `meta.json` summary first → obvious C/D judged directly; suspected A/B gets paper.md deep-read (first ~120 + last ~80 lines).
- **Ledger appends serialized**: workers report back; main session appends TRIAGE.md rows (parallel appends would clobber).
- Relevance lens: pure option pricing / insurance / DeFi / credit scoring / FX micro-structure grade C/D regardless of quality.
