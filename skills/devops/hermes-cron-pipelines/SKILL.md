---
name: hermes-cron-pipelines
description: Build, debug, and add fallbacks to Hermes cron jobs that drive data pipelines — direct jobs.json editing, multi-source degradation, and no-Python bash pipelines.
version: 1.0.0
tags: [hermes, cron, data-pipeline, fallback, jq, sqlite, bash]
---

# Hermes Cron Data Pipelines

## Trigger Conditions

When:
- Creating or modifying a Hermes cron job that fetches financial / API data
- Adding fallback / degradation logic to an existing data-pipeline cron job
- The `hermes cron` CLI is blocked (macOS TCC sandbox, remote backend, etc.)
- Building bash-based data pipelines that must work without Python
- Debugging a cron job that involves web data sources

## Key Concepts

### Agent Job vs Script Job

| Type | `no_agent` | Pros | Cons | When to use |
|------|-----------|------|------|-------------|
| Agent | `false` | Flexible, adapts to API changes, can self-debug | Slower, token cost, prompt must be explicit | Multi-source, fallback logic, complex parsing |
| Script | `true` | Fast, deterministic, low cost | Brittle, needs updates for API changes | Simple, stable API endpoints |

**Rule of thumb**: If the pipeline has >1 data source or complex error handling, use an Agent job.

### Direct jobs.json Editing (When CLI is Blocked)

The `hermes cron edit` CLI command may fail due to macOS TCC sandbox (`/var/folders/...` not writable). The canonical backup approach:

```bash
# 1. Create new prompt content in a temp file (in writable directory)
# 2. Use jq --rawfile to replace just the target job's prompt
jq --rawfile newprompt /path/to/new_prompt.txt \
  '.jobs |= map(if .id == "JOB_ID" then .prompt = $newprompt else . end)' \
  ~/.hermes/cron/jobs.json > ~/.hermes/cron/jobs.json.tmp \
  && mv ~/.hermes/cron/jobs.json.tmp ~/.hermes/cron/jobs.json

# 3. Verify JSON validity
jq empty ~/.hermes/cron/jobs.json

# 4. Verify key fields preserved
jq '.jobs[] | select(.id == "JOB_ID") | {id, schedule, enabled, no_agent}' \
  ~/.hermes/cron/jobs.json
```

**Pitfall**: Never modify schedule, `script`, `no_agent`, or `workdir` during a fallback-only edit. Only change `prompt`.

## Multi-Source Fallback Pattern

### Degradation Trigger Conditions

Define clear, quantitative triggers before the agent starts. The agent checks these after every batch:

```
Tier-1 triggers (fatal — switch immediately):
  - ≥60% of URLs in a batch return 502/403/connection error/empty JSON
  - Any web_extract response body contains "502 Bad Gateway"

Tier-2 triggers (aggregate — switch after 3 batches):
  - ≥67% of stocks in first 3 batches have null/empty data
  - >50% of all attempted stocks have zero records

Fallback activation: stop all primary-source requests, switch entirely to secondary.
```

### Bash Pipeline Without Python

When Python is unavailable (missing xcode-select, no venv), build the write pipeline with:

| Tool | Role |
|------|------|
| `curl` | HTTP requests (API calls) |
| `jq` | JSON parsing, field extraction, array iteration |
| `bc -l` | Arithmetic (field calculations, sign splitting) |
| `sqlite3` | Database INSERT OR REPLACE |
| `openssl rand -hex 32` | Random trace IDs for API auth |
| `sed` | String manipulation (strip suffixes like .SH/.SZ) |

**Pattern for field extraction + calculation + write**:

```bash
echo "$RESP" | jq -r '.datas[] | [.field1 // "0", .field2 // "0", .code // ""] | @tsv' \
  | while IFS=$'\t' read val1 val2 code; do
    [ -z "$code" ] && continue
    derived=$(echo "$val1 + $val2" | bc -l)
    sqlite3 db.sqlite "INSERT OR REPLACE INTO table (code, date, val)
      VALUES ('$code', '$TODAY', $derived);"
  done
```

### Data Source Identity

Always tag records with `data_source` to distinguish origin:

```
data_source = 'eastmoney'  → primary source
data_source = 'iwencai'    → fallback source
```

This enables downstream queries to filter/highlight degraded data.

## Reference Files

- `references/moneyflow-fallback-eastmoney-to-iwencai.md` — Complete worked example: 东财 push2his → 问财 OpenAPI 资金流 fallback pipeline with field mappings, bash scripts, and SQLite schema.

## Key Pitfalls

1. **macOS TCC sandbox blocks `/var/folders/...`**: Terminal commands may fail with "Operation not permitted" for temp files. Use user home directories for temp files instead.
2. **Python may be absent**: `xcode-select` issues on macOS can break `/usr/bin/python3`. Test availability before using Python in cron pipelines; prefer `jq`+`bc`+`sqlite3`.
3. **Secret redaction in terminal output**: `grep IWENCAI_API_KEY ~/.hermes/.env` lines in terminal output get redacted to `***`. This is normal — the actual file content is unchanged.
4. **Prompt size explosion**: Fallback instructions can double prompt size. For Agent jobs this increases token cost per run. Keep bash snippets in the prompt concise; avoid duplication.
5. **Batch size differences between sources**: 东财 push2his is per-stock (batch 4-5 URLs), 问财 is batch-query (15-20 stocks/comma-separated). The prompt must include both batch patterns.
6. **Field mapping differences**: Primary and fallback sources rarely have identical field schemas. Document the mapping explicitly in the prompt with formulas (e.g., `main_net = elg + lg` for 问财 fallback).
