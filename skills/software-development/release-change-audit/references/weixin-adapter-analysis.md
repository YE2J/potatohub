# Weixin/iLink Adapter Analysis Reference

## Session Context

Analysis of Hermes v0.18.0 vs weixin rate-limit issues. Methodology captured in the parent SKILL.md; this reference holds domain-specific knowledge about the weixin adapter internals.

## Version Timeline

| Version | Date | Key Weixin Changes |
|---------|------|--------------------|
| v2026.6.19 | 2026-06-19 | **All rate-limit improvements shipped here**: circuit breaker (`b8469a81e`), typing ticket refresh, `asyncio.wait_for()` migration, stale-session detection, descriptive rate-limit errors |
| v0.18.0 | 2026-07-01 | Zero weixin rate-limit changes. Only: DM policy default `open→pairing`, `splits_long_messages=True`, `is_reconnect` param, intake auth refactor |

## Verified Rate-Limit Architecture

Source: `gateway/platforms/weixin.py` (HEAD at v0.18.0)

### Circuit Breaker Parameters

All tunable via `config.yaml` under `platforms.weixin.extra.` or env vars:

| Parameter | Default | Environment Variable |
|-----------|---------|---------------------|
| `rate_limit_circuit_threshold` | 1 | `WEIXIN_RATE_LIMIT_CIRCUIT_THRESHOLD` |
| `rate_limit_circuit_window_seconds` | 30.0 | `WEIXIN_RATE_LIMIT_CIRCUIT_WINDOW_SECONDS` |
| `rate_limit_circuit_open_seconds` | 30.0 | `WEIXIN_RATE_LIMIT_CIRCUIT_OPEN_SECONDS` |
| `send_chunk_delay_seconds` | 1.5 | `WEIXIN_SEND_CHUNK_DELAY_SECONDS` |
| `send_chunk_retries` | 4 | `WEIXIN_SEND_CHUNK_RETRIES` |
| `send_chunk_retry_delay_seconds` | 1.0 | `WEIXIN_SEND_CHUNK_RETRY_DELAY_SECONDS` |

### Critical Identified Gaps

1. **Circuit breaker state is in-memory only** (`_rate_limit_circuit_until: float`) — gateway restart (launchd, crash) resets it to zero
2. **No DNS-recovery grace period** — after `BACKOFF_DELAY_SECONDS=30` following 3 consecutive failures, polling loop resumes full speed immediately
3. **No exponential backoff** — polling loop uses fixed `BACKOFF_DELAY_SECONDS=30`, not multiplying on repeated failures
4. **Server-side iLink rate-limit is independent** — client-side breaker prevents retry storms, but cannot prevent iLink from rejecting the first send after a DNS outage

### Error Classification

iLink return codes:

| Code | Meaning | Action |
|------|---------|--------|
| `ret=-2`, `errcode=-2`, `errmsg="unknown error"` | **Stale session** (not rate-limit!) | Strip `context_token`, retry once |
| `ret=-2`, `errcode=-2`, other errmsg | **Rate limit** | Record event, maybe open circuit breaker, backoff 3x, retry |
| `errcode=-14` | **Session expired** | Same as stale-session path |
| `ret=-14` | **Session expired** | Poll loop pauses 10 minutes |

## Gateway Log Pattern for DNS + Rate-Limit Cascade

From `~/.hermes/logs/gateway.error.log`:

```
# Phase 1: DNS outage (hit repeatedly)
ERROR [Weixin] poll error (3/3): Cannot connect to host ilinkai.weixin.qq.com:443
  ssl:default [nodename nor servname provided, or not known]

# Phase 2: DNS recovers, send attempts flood, get rate-limited
WARNING [Weixin] send chunk failed to=o9cq805u attempt=1/5, retrying in 1.00s:
  Cannot connect to host ilinkai.weixin.qq.com:443
WARNING [Weixin] send chunk failed to=o9cq805u attempt=2/5, retrying in 2.00s:
  Cannot connect to host ilinkai.weixin.qq.com:443
ERROR   [Weixin] send failed to=o9cq805u: iLink sendmessage rate limited;
  cooldown active for 30.0s

# Phase 3: Gateway restarts (circuit breaker lost)
INFO  [Weixin] Disconnected                          # ~5-16s after rate-limit
INFO  ✓ weixin disconnected
INFO  Connecting to weixin...
INFO  ✓ weixin connected

# Phase 4: Immediately rate-limited again
ERROR [Weixin] send failed to=o9cq805u: iLink sendmessage rate limited;
  cooldown active for 30.0s
```

## Mitigations for Users

If experiencing this pattern, suggest these config changes in order of effectiveness:

1. **Increase circuit breaker cooldown** — gives iLink server more time to reset its own window:
```yaml
platforms:
  weixin:
    extra:
      rate_limit_circuit_open_seconds: 120
```

2. **Slow down chunk delivery** — prevents burst sends:
```yaml
platforms:
  weixin:
    extra:
      send_chunk_delay_seconds: 3.0
```

3. **Increase retry backoff** — reduces server pressure:
```yaml
platforms:
  weixin:
    extra:
      send_chunk_retry_delay_seconds: 3.0
```

4. **Throttle launchd restart** — give server-side rate-limit time to expire:
```bash
# Edit the gateway service to add RestartSec
hermes config set gateway.restart_sec 60
```
