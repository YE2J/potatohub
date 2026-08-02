# Daily Wiki Auto-Update Pipeline (cron)

The `~/.hermes/wiki/` LLM wiki (Karpathy-style, see bundled `llm-wiki` skill for the generic pattern)
is refreshed by a daily cron that reads the quant pipeline state and appends to 4 pages.
This file records the implementation-specific pitfalls discovered while running that cron.

## Wiki Layout (A-share quant domain)

```
~/.hermes/wiki/
├── SCHEMA.md          # domain conventions, tag taxonomy, frontmatter rules
├── index.md           # catalog with "最后更新: YYYY-MM-DD | 总页数: N" header
├── log.md             # append-only, format: "## [YYYY-MM-DD] action | subject"
├── concepts/
│   ├── 每日盘面.md      # daily market summary (K线/资金流/指数/L1温度/估值)
│   ├── 资金流追踪.md    # watchlist moneyflow top-N
│   └── 估值动态.md      # valuation staleness tracker
└── Hermes/
    └── 日报归档.md      # weekly-archived daily report digest
```

## Cron Execution Steps

1. **Orient**: read `SCHEMA.md` → `index.md` → `log.md` (last 20-30 lines). Do NOT skip — prevents duplicate pages / missing cross-refs.
2. **Collect data**:
   - Morning report: `~/.hermes/cron/output/3cb6fbcc8dcc/` (latest `*.md`, job id = 每日晨报采集, ~07:05)
   - Pipeline run status: scan `~/.hermes/cron/output/` newest files per job id (see `a-share-data-pipeline-check` SKILL.md for job-id map)
   - DB freshness: `sqlite3 ~/my_quant_system/stock_data.db` — MAX(date) per table, ALWAYS pair with COUNT(*) (partial-write detection)
3. **Update 4 pages** (append new dated section, never overwrite prior sections):
   - `concepts/每日盘面.md` — market summary
   - `concepts/资金流追踪.md` — moneyflow top5
   - `concepts/估值动态.md` — valuation staleness days
   - `Hermes/日报归档.md` — digest section
4. **Update navigation**: bump `index.md` "最后更新" date.
5. **Log**: prepend `## [YYYY-MM-DD] update | Daily wiki auto-update` to `log.md`.

## Pitfalls (each cost real effort once)

### 1. Append-only updates CLOBBER frontmatter — verify & restore
On 2026-08-01, `concepts/资金流追踪.md` was found with **no frontmatter** — the first line was a
leftover table row (`|||| 估值 data_as_of | 07-12（15 日 ⏳） |`). An earlier append operation had
replaced the YAML block. Fix: re-add frontmatter manually:

```yaml
---
title: 资金流追踪
created: 2026-06-25
updated: 2026-08-01
type: concept
category: A股量化
tags: [stock, fund-flow]
sources: [量化系统/数据管线.md]
---
```

**Checklist**: after every edit, run `head -5 <page>` and confirm the `---` + title block survived.
If the file starts mid-table or mid-heading, restore the frontmatter before appending.

### 2. `updated:` frontmatter bump is a separate, easy-to-forget step
SCHEMA says "bump the `updated` date when updating a page" but the cron narrative sections don't
remind you. Always do a second pass: patch `updated: YYYY-MM-DD` in all 4 pages to today's date.
Forgetting it makes the wiki look stale and breaks staleness linting.

### 3. Date-format double standard inside one DB
`margin_balance.trade_date` = `YYYYMMDD` (e.g. `20260730`) while `daily_kline.date` /
`moneyflow_daily.date` = `YYYY-MM-DD`. When reporting 两融 vs K线 dates, keep formats consistent
in the same table cell — mixing `07-30` and `20260730` confuses readers.

### 4. Diagnose mass pipeline failure from cron output BEFORE touching the DB
When 10+ pipelines fail the same evening, read their cron output files first — stderr tracebacks
point at the shared root cause (`db_utils.py get_conn` → `sqlite3.OperationalError: unable to open
database file`). The 两融诊断/外置盘诊断 one-off jobs (`47c218bf809d`, `da719983a44d`) print the
`DB symlink:` state directly. Full diagnostic branch: see `a-share-data-pipeline-check` SKILL.md
"Symlink → External Drive (TCC)" section.

### 5. Distinguish "data missing" vs "weekend" honestly
Saturday/Sunday cron runs have NO new trading data by definition. Report as "周六无新交易数据"
and note the pipeline's last-data date + staleness days (e.g. 估值 20 日) — do not mark the
pipelines as failing for doing nothing on a weekend.

### 6. Cron task prompt's hardcoded job dir can go stale — DB is the ground truth
The cron prompt may reference a Hermes-daily-report dir like
`~/.hermes/cron/output/c448b2045f93/` that **no longer exists** (cron_log_cleanup prunes
old output dirs; Coze 日报 has been missing since 07-02). Don't burn time hunting it —
the reliable sources are: morning report `~/.hermes/cron/output/3cb6fbcc8dcc/` (每日晨报采集)
+ the DB itself. If a prompt-referenced path doesn't exist, note it in log.md and move on
(verified 2026-08-02).

### 7. Wiki cron runs ~03:00 — today's 07:05 morning report doesn't exist yet
The wiki cron fires at ~03:00-04:00, BEFORE the daily morning report (07:05) is generated.
The latest morning-report file available is ALWAYS yesterday's. Don't record "no morning
report" as a failure; say "今日晨报尚未生成（cron 运行于凌晨，昨日晨报为最新）".

### 8. patch tool can silently corrupt `||`-prefixed table rows — verify pipe counts
Wiki pages use markdown tables whose rows start with `||`. When appending via `patch`,
fuzzy matching can rewrite the pipe count at the edit boundary (e.g. `|| 遗留问题` became
`||| 遗留问题` on 2026-08-02), breaking row alignment. Mitigation: copy the anchor line
from the file verbatim (don't retype pipe counts), and after patching, `grep -n '^|||'`
(or view the tail) to confirm the edited rows match the surrounding rows' prefix.

### 9. Query each tracked table directly — L1 温度 can advance while other tables lag
On 2026-08-01, the run reported "07-30/07-31 缺失" based on kline/moneyflow dates, but
`market_temperature` actually HAD 07-30 (17.1 冰点) and 07-31 (37.7) — the L1 engine
recomputed independently after the backfill. Never infer one table's freshness from
another's; `SELECT trade_date, temperature_score ... ORDER BY trade_date DESC LIMIT 3`
on `market_temperature` is cheap and settles it. This is the wiki-side instance of the
"Independent Freshness" doctrine in the SKILL.md.

## Reporting convention (cron delivery)
Final response should lead with the headline finding (e.g. "W31 收官日数据全线缺失"), then a
data-freshness table, then what was updated. Use emoji status consistently (🚀 new / ✅ ok / 🔴 fail).
