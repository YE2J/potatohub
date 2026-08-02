# iLink Rate Limit Fix — Design Summary

## Problem
iLink rate limiting (30s cooldown) blocks morning report WeChat pushes. Root cause: DNS transient failure → 5 gateway retries → iLink server-side rate limit → subsequent cron runs reset cooldown → lock.

| Metric | Count |
|--------|-------|
| Rate limit hits in logs | 91 |
| Preceding DNS failures | 148 |

## Architecture

```
07:00 → no_agent script → collect data → save to pending/ (deliver: local)
07:02 → health check → if healthy: push pending (deliver: origin), else cache
08:00 → retry #1 (30min backoff) → health check → push if healthy
09:00 → retry #2 (60min backoff) → health check → push if healthy
12:00 → cleanup expired markers
```

## New Scripts (in `scripts/`)

| Script | Purpose |
|--------|---------|
| `ilink_health.sh` | Pre-flight: DNS + TCP + recent rate-limit check. Exit 0/1/2/3 |
| `delivery_retry.sh` | Pending queue drainer with exponential backoff |
| `dns_harden.sh` | Daily DNS pre-cache for macOS launchd environments |
| `cleanup_delivery.sh` | Expire old markers, alert on ≥3 abandoned reports in 7 days |

## Priority

| Item | Priority | Status |
|------|----------|--------|
| Pre-flight health check | P0 | ✅ `ilink_health.sh` + `delivery_retry.sh` |
| Async retry queue | P0 | ✅ `delivery_retry.sh` + cron entries |
| DNS caching | P1 | ✅ `dns_harden.sh` |
| Email fallback | P1 | ⬜ Needs msmtp + config |
| Gateway auto-recovery | P2 | ⬜ Future |
| Telegram fallback | P3 | ⬜ If configured |

## Key Design Decisions

- **Stop hammering cooldown**: Try once per cron tick, never retry in-loop
- **`[SILENT]` suppression**: `no_agent=true` scripts output `[SILENT]` when unhealthy → cron skips delivery
- **Exponential backoff over fixed intervals**: 30min → 60min → 120min → abandon at 3 retries
- **Pending queue FIFO**: Oldest report gets delivered first when channel recovers
