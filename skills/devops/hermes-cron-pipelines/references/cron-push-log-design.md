# Cron Push Logging & Audit Trail — Design Reference

## Why DB-Backed Logging?

Each no_agent cron job writes to `~/.logs/*.log` via ad-hoc shell wrappers. There was:
- **No unified query interface** — grep across 10+ log files
- **No delivery audit** — you couldn't tell if a push succeeded from the DB
- **No content size tracking** — couldn't see output growth over time
- **No retention policy** — logs accumulated forever

The `etl_runs` table existed for legacy Coze/old-moneyflow jobs but didn't cover the new Tushare+factor pipeline scripts. 

## Schema: cron_push_log

```sql
CREATE TABLE cron_push_log (
    log_id           INTEGER PRIMARY KEY AUTOINCREMENT,
    job_name         TEXT NOT NULL,             -- '每日晨报采集' / '前复权日线-Tushare增量'
    job_id           TEXT,                      -- Hermes cron job_id (optional)
    scheduled_time   DATETIME NOT NULL,         -- cron 预期执行时间
    actual_time      DATETIME,                  -- 脚本实际开始时间
    finished_time    DATETIME,                  -- 脚本结束时间
    status           TEXT NOT NULL DEFAULT 'running',  -- 'running'/'success'/'failed'/'timeout'/'skipped'
    duration_ms      INTEGER,                   -- 执行耗时(毫秒)
    exit_code        INTEGER,                   -- 脚本 exit code
    delivery_channel TEXT DEFAULT 'local',      -- 'local' / 'weixin' / 'webhook'
    delivery_status  TEXT,                      -- 'pending' / 'delivered' / 'failed' / 'n/a'
    content_path     TEXT,                      -- 内容文件绝对路径 (方案A: 只存路径)
    content_size     INTEGER,                   -- 文件大小(字节)
    content_hash     TEXT,                      -- SHA256 文件校验 (可选)
    error_message    TEXT,                      -- 失败/超时原因
    log_tail         TEXT,                      -- 脚本最后 20 行 stdout
    trigger_type     TEXT DEFAULT 'cron',       -- 'cron' / 'manual' / 'retry'
    created_at       DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

## Content Storage: Why File Paths, Not BLOBs

| Dimension | Pure File Path (chosen) | DB BLOB/TEXT |
|-----------|------------------------|--------------|
| DB growth | Zero growth per run | ~1-7KB/run, ~3MB/year |
| Backup | DB stays ~4.4GB | Grows with every run |
| Debug speed | `cat $path` instantly | `SELECT content FROM ...` |
| Cleanup | OS `find -mtime +30 -delete` | `DELETE + VACUUM` |
| Migration | Rename path, update DB | Dump/restore entire set |

Decision: **Store content_path only**. The existing Hermes cron output mechanism (`~/.hermes/cron/output/<job_id>/<timestamp>.md`) already captures stdout. Point to it.

## cron_log_helper.sh Pattern

source-based helper with 4 functions:

```
cron_log_init(job_name, job_id, scheduled_time, delivery_channel)
  → INSERT cron_push_log row, return log_id

cron_log_finish(exit_code, [status], [content_path])
  → UPDATE same row with duration_ms, log_tail, status

cron_log_tail
  → pipe modifier: tee -a $CRON_TEMP_LOG (captures stdout for log_tail)

cron_log_error(message)
  → UPDATE error_message column on an existing row
```

**Usage in any no_agent wrapper:**

```bash
source "$HOME/.hermes/scripts/cron_log_helper.sh"
cron_log_init "任务名" "job-id" "HH:MM" "local"

run_pipeline 2>&1 | cron_log_tail
RC=${PIPESTATUS[0]}

cron_log_finish $RC "" "/path/to/output.md"
exit $RC
```

## Retry Pattern for deliver=weixin Jobs

Morning report (the only weixin job) has special handling:

1. `cron_log_init` with `delivery_channel='weixin'`
2. Content points to `~/.hermes/delivery/pending/<date>_晨报.md`
3. If delivery fails, the `cron_push_log` shows `delivery_status='pending'`
4. Retry jobs (08:00/09:00) create new rows with `trigger_type='retry'`
5. After 3 failed delivery attempts, convert to `.abandoned`

The `cron_push_log` does NOT track `.done`/`.abandoned` state — that stays in the file-system pending directory. The DB tracks the delivery attempt itself.

## Cleanup Policy

| Data | Retention | Method |
|------|-----------|--------|
| success/skipped records | 60 days | `DELETE WHERE created_at < now - 60d` |
| failed records | 180 days | `DELETE WHERE created_at < now - 180d` |
| running zombie records | 7 days | `DELETE WHERE status='running' AND created_at < now - 7d` |
| Content files | 30 days | OS-level `find -mtime +30 -delete` |

Cleanup runs via a dedicated cron Log cleanup job: `cron_log_cleanup.sh` (Sunday 03:00).

## Migration from etl_runs

The legacy `etl_runs` table exists with 35 historical records across 4 job types:
- coze_daily_report → "Coze 日报生成"
- daily_moneyflow → "资金流向-旧(同花顺)"
- db_backup → "数据库备份"
- weekly_valuation → "周估值运行"

Migration preserves `etl_runs` (read by Coze scripts) while populating `cron_push_log` for unified querying. Run once: `migrate_etl_runs_to_cron_push_log.py`.

## Useful Queries

```sql
-- Today's run status
SELECT job_name, status, duration_ms, delivery_channel
FROM cron_push_log
WHERE scheduled_time >= date('now')
ORDER BY scheduled_time;

-- Last 7 days failures
SELECT job_name, scheduled_time, error_message
FROM cron_push_log
WHERE status = 'failed' AND created_at >= datetime('now', '-7 days');

-- 30-day success rate
SELECT job_name, COUNT(*) total,
       SUM(CASE WHEN status='success' THEN 1 ELSE 0 END) success,
       ROUND(100.0 * SUM(CASE WHEN status='success' THEN 1 ELSE 0 END) / COUNT(*), 1) rate,
       ROUND(AVG(duration_ms) / 1000.0, 1) avg_sec
FROM cron_push_log
WHERE created_at >= datetime('now', '-30 days')
GROUP BY job_name;
```

## Staggered Scheduling Principle

When multiple cron jobs form a pipeline with implicit data dependencies:

1. **No two jobs at same `:00` minute** — avoid Hermes cron concurrency
2. **Minimum 30min gap** between dependent jobs
3. **No hard dependency chain** — downstream jobs self-check data readiness
4. **Off-:00 starts** (07:02, 18:30) — avoid system-wide cron bursts

Example pipeline order:
```
00:00  DNS cache
07:02  Morning report
12:00  Delivery cleanup
18:00  K-line (primary data pull)
18:30  Money flow (independent of k-line)
19:00  Factor update (reads both k-line + moneyflow)
20:00  Factor backfill (historical, runs last)
```
