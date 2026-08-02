# 晨报 v5.2 — Self-Contained Python Report (no_agent)

## Current Architecture (v5.2, 2026-07-07)

```
07:02 → cron runs daily_morning_report_v5.py (no_agent=true)
       → script queries stock_data.db (SQLite) for moneyflow data
       → script reads ~/.hermes/cron/output/<job_id>/ for task summaries
       → script checks ~/.logs/ for pipeline freshness
       → stdout = complete report → cron delivers to WeChat (deliver=origin)
```

**This is NOT agent-driven.** It is a pure Python script that reads local files only. Zero network calls.

## Output Modules

| Module | Emoji | Data source | What it shows |
|--------|-------|-------------|---------------|
| 资金流向 | 💰 | `moneyflow_daily` + `hsgt_moneyflow` (SQLite) | 主力净流入/流出总额, TOP5买入/卖出, 北向资金 |
| 昨日任务概览 | 📋 | `~/.hermes/cron/output/<job_id>/` | 12 cron tasks status/summary, Hermes日报摘要 |
| 数据采集状态 | ⚙️ | `~/.logs/*.log` file timestamps | 4 core pipeline freshness |

### Removed modules (v5.1→v5.2):
- ❌ 大盘概况 — removed 2026-07-07
- ❌ 行业板块 — removed 2026-07-07
- ❌ 自选股表现 — removed 2026-07-07

## Cron Output Reading Pattern

The `report_yesterday_tasks()` module reads from `~/.hermes/cron/output/<job_id>/`:

```python
CRON_JOBS = [
    ("0c029d10767b",  "📊 前复权日线",     "qfq_tushare_daily.sh"),
    ("910124571b2d",  "💰 资金流向(DC)",    "daily_moneyflow_tushare_dc.sh"),
    ("5575f1bae80e",  "📊 指数日线",       "daily_index_tushare.sh"),
    ("263ec7d6d324",  "📈 因子更新",        "daily_factor_update.sh"),
    ("33a1981e50d3",  "🔥 个股异动(同花顺)","daily_anomaly_fuyao.sh"),
    ("cfb84613007b",  "🚀 涨停池(同花顺)",  "daily_limit_up_fuyao.sh"),
    ("e234625f83ff",  "🔗 连板天梯(同花顺)","daily_limit_up_ladder.sh"),
    ("d550bbebb2ff",  "🏆 龙虎榜(同花顺)",  "daily_dragon_tiger_fuyao.sh"),
    ("395cb3e7080b",  "🌐 市场热榜(同花顺)","daily_hot_stock_fuyao.sh"),
    ("cddbbd144447",  "📊 因子回填",        "backfill_chunk.sh"),
    ("82d135d6a369",  "📚 Wiki增量",        "llm-wiki"),
    ("db18b3fced2e",  "🧹 晨报清理",        "cleanup_delivery.sh"),
]
```

Each cron job's output file (`~/.hermes/cron/output/<job_id>/<latest>.md`) contains markdown with structured data. The parser extracts:

1. **Write counts**: `✅ 写入 N 条` pattern
2. **DONE lines**: `DONE: YYYY-MM-DD → N 只股票写入 table_name`
3. **Backfill status**: `[BACKFILL COMPLETE] start → end`

### Metrics extraction function

```python
def cron_extract_metrics(content):
    metrics = []
    for line in content.split('\n'):
        m = re.search(r'✅\s*(?:写入|已写入)\s*(\d+)\s*条', line)
        if m:
            metrics.append(f"写入 {m.group(1)} 条")
    for line in content.split('\n'):
        if 'DONE:' in line:
            metrics.append(line.strip()[:80])
    for line in content.split('\n'):
        if '[BACKFILL COMPLETE]' in line:
            metrics.append(line.strip()[:60])
    return metrics if metrics else []
```

### Status freshness thresholds

| Age | Icon | Meaning |
|-----|------|---------|
| ≤30h | ✅ | Fresh |
| 30-48h | ⚠️ | Stale |
| >48h | ❌ | Dead |

### Pitfall: hardcoded job_ids

`CRON_JOBS` contains hardcoded Hermes cron job IDs. If the Hermes cron system is rebuilt (migration, reinstall), these IDs change and ALL tasks show "无运行记录". Future improvement: read from `~/.hermes/cron/jobs.json` and match by name instead.

### Pitfall: financial-api cron output format stability

Financial-API cron jobs (涨停池, 龙虎榜, 个股异动, etc.) produce format-stable output like `✅ 写入 N 条`. If the shell script output format changes (e.g. "✅ 写入 N 条" → "已成功写入 N 条记录"), the regex-based parser silently returns empty metrics. The table shows blank "简情" columns, which is confusing but non-fatal.

## Cron Integration

```bash
# Current config (2026-07-07)
hermes cron action=update \
  job_id="3841106d9ea2" \
  script="daily_morning_report_v5.py" \
  no_agent=true \
  deliver=origin \
  schedule="2 7 * * *"
```

## Output Constraints for WeChat

- **3800 char hard limit** — iLink WeChat channel caps at ~4000 chars; v5.2 script truncates at 3800
- **emoji + table format** — one emoji per section, markdown tables for structured data
- **Truncation**: when over limit, script cuts from bottom and appends "⚠️ 超出字数限制, 已截断"
- **Current output**: ~1350 chars (well under limit)

## Key Design Decisions

1. **no_agent=true** — deterministic, fast, zero token cost, no LLM overhead
2. **All data from local filesystem** — SQLite DB + cron output dirs + log files. No network calls
3. **Separate cron output reading from pipeline logging** — the `~/.logs/` files are used for freshness (`report_data_status`), while `~/.hermes/cron/output/` files provide detailed metrics (`report_yesterday_tasks`)
4. **Hermes日报摘要** — reads `~/quant_shared/daily_reports/<yesterday>_hermes.md` for the "昨日工作回顾" section

## Comparison with Earlier Versions

| Aspect | v4 (retired) | v5.0 (superseded) | v5.2 (current) |
|--------|-------------|-------------------|----------------|
| Engine | bash + grep logs | Python + SQLite | Python + SQLite |
| Content | Pipeline log lines | 大盘+板块+资金+自选+状态 | 💰资金+📋任务+⚙️状态 |
| Data sources | Log files only | DB + Sina API | DB + cron output + logs |
| Network required | No | Yes (Sina API) | No |
| Delivery | Pending queue + retry crons | Direct stdout | Direct stdout |
| Output size | ~400 chars | ~1300 chars | ~1350 chars |

## File Location

```
~/.hermes/scripts/daily_morning_report_v5.py  — the script (415 lines)
```

The script name still says "v5" but the content is v5.2. Renaming would break the cron reference — update cron first if renaming.
