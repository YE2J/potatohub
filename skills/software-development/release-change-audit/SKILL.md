---
name: release-change-audit
description: "Verify whether a new software release actually addresses a reported issue by correlating git history, source code diffs, and runtime logs. Use when a user reports 'did version X fix Y?' — do not guess from release notes alone."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [release-analysis, verification, git-diff, log-analysis, change-audit]
    related_skills: [systematic-debugging, hermes-agent]
---

# Release Change Audit

## Overview

When a user asks "does the new version fix my issue?" — release notes are unreliable. Feature descriptions may not apply, bug fixes may have been shipped in a *previous* release, and the same code may have different behavior under different configurations.

This skill provides a systematic methodology for evaluating whether a new software version actually changes anything relevant to a reported problem. It correlates three sources of truth: **source code**, **git history**, and **runtime logs**.

Reference: a worked example of this methodology applied to the Hermes Weixin/iLink rate-limit issue exists at `skill_view(name="release-change-audit", file_path="references/weixin-adapter-analysis.md")`. It includes the exact error cascade, circuit breaker parameters, and mitigations for the DNS-flapping + rate-limit pattern.

## When to Use

- User asks "will upgrading to version X fix my problem?"
- User reports an ongoing issue and asks if a specific release addresses it
- You need to evaluate whether a fix was actually shipped in a given release
- Comparing configuration defaults between versions
- Understanding what an adapter or component actually does vs what documentation claims

Do NOT use for:
- General debugging (use `systematic-debugging`)
- Bug reproduction or root cause analysis
- Code review of a new feature
- Performance benchmarking

## The Workflow

### Phase 1: Find the Version Boundaries

```bash
# In the repo directory:
git tag | sort -V | tail -10        # See all releases in order
git log --oneline -1                 # What HEAD is currently at
```

Identify:
- The **old version** the user was on (or the last known-good version)
- The **new version** they're asking about
- Check if tags exist or if you need to use commit hashes

```bash
git log vOLD..vNEW --oneline         # All commits between releases
```

### Phase 2: Search for Feature-Specific Commits

Grep the git log for anything related to the user's concern:

```bash
# Broad search across all history
git log --all --oneline --grep="feature_name\|platform\|error_code\|key_term" --since="YYYY-MM-DD"

# Narrow search between the versions
git log --all --oneline --grep="search_terms" vOLD..vNEW
```

**Critical check**: determine which release first included each relevant commit:

```bash
for hash in COMMIT1 COMMIT2 COMMIT3; do
  echo "$hash: $(git tag --contains $hash | sort -V | tail -1)"
done
```

If a fix commit was shipped in a **previous** release, the current release cannot be the one that added it.

### Phase 3: Diff the Relevant Files

```bash
# Measure the total change to the component
git diff vOLD..vNEW -- path/to/component.py | wc -l

# Inspect the actual changes
git diff vOLD..vNEW -- path/to/component.py
```

**Key questions**:
- Is the diff large enough to contain a substantive change?
- Do any of the changed lines touch the area the user is asking about?
- Could configuration defaults have changed without code changes?

For config-default changes, also check:
```bash
git diff vOLD..vNEW -- tools/send_message_tool.py  # Send path changes
git diff vOLD..vNEW -- gateway/config.py            # Config default changes
```

### Phase 4: Read the Source Implementation

Read the actual code that governs the user's concern. Do not rely on function names or docstrings — verify the behavior:

- **Rate limiting**: Look for sliding window tracking, threshold, cooldown timeouts, serialization gates
- **Retry logic**: Retry count, backoff multiplier, error classification
- **Timeouts**: `asyncio.wait_for()` vs `aiohttp.ClientTimeout` — these behave differently across runtimes (`run_coroutine_threadsafe`)
- **Connection handling**: SSL configuration, DNS resolution, session lifecycle
- **Error handling**: How are transient vs fatal errors classified?

Focus on the methods called during the user's specific workflow (polling loop, send path, reconnect logic).

### Phase 5: Correlate with Runtime Logs

Gateway logs are the ground truth for messaging platform issues:

```bash
# Main gateway log
grep -i "platform\|error\|rate.limit\|timeout\|disconnect" ~/.hermes/logs/gateway.log

# Error log (more detailed)
grep -i "platform\|nodename\|cannot connect\|timeout\|errcode" ~/.hermes/logs/gateway.error.log
```

**Identify the complete error chain** — not just the final error the user sees, but the cascade that leads to it:

```
DNS failure → send retries fail → circuit breaker opens → cooldown → 
disconnect → auto-restart → breaker state lost → send fails again
```

**The chain tells you the real problem**, not the last link.

### Phase 6: Form the Evaluation

Combine evidence from all phases into a clear assessment:

1. **Does the new version contain code changes in the relevant area?** (Phase 3)
2. **Were those changes already shipped earlier?** (Phase 2)
3. **If new changes exist, do they address the root cause visible in logs?** (Phase 4 + 5)
4. **Are there architectural gaps that no code change in this release could fix?** (Phase 4)

Possible conclusions:
- ✅ **Fixed**: The new version contains relevant changes that directly address the logged symptom
- ⚠️ **Partially addressed**: Changes exist but don't cover all cases (e.g., client-side fix but server-side issue remains)
- ❌ **Not changed**: No relevant code changes between versions
- 🔄 **Already shipped**: The fix was in a previous version; the user's issue has a different cause
- 🏗️ **Architectural gap**: The problem requires structural changes not present in any current version

## Common Patterns

### Circuit Breaker Architecture

Many network adapters use a circuit breaker pattern:

```
Event counter (sliding window) → threshold check → breaker opens (cooldown timer) → 
all sends aborted early → cooldown expires → circuit resets → normal sends resume
```

**Key gap**: Circuit breaker state is usually in-memory. A process restart resets it to zero. If the server-side rate-limit outlasts the restart, the problem recurs immediately.

### DNS Flapping + Rate Limits

The cascade is characteristic:
1. DNS resolution fails intermittently
2. No sends are attempted during DNS failure
3. DNS recovers → all pending sends flood out at once
4. Server sees burst → rate-limits the client
5. Client's circuit breaker opens
6. If client restarts, breaker state is lost → back to step 4

**Fix**: Add DNS-recovery grace period (no sends for N seconds after a DNS failure resolves), persist breaker state to disk.

### Restart Cycle Amplification

When a gateway auto-restarts (systemd/launchd `Restart=on-failure`) too quickly:
- Each restart resets in-memory state (circuit breaker, rate-limit counters)
- Each restart retries the same pending sends
- Each retry hits the same server-side rate limit
- Each failure triggers another restart
- Cycle continues until manual intervention or server-side rate limit expires

**Fix**: Increase `RestartSec` in the service file, persist throttling state across restarts, or add a grace period on startup.

## Pitfalls

- **Release tag availability**: Some projects don't tag every release. Use commit date ranges as fallback.
- **Merge commits**: Search merged PR descriptions, not just commit subject lines.
- **Configuration defaults can change in config.py or env var parsers**: Check all config-related files, not just the adapter.
- **Dependency bumps**: A transitive dependency update can fix issues without any adapter code changing. Check `git diff vOLD..vNEW -- pyproject.toml` or similar.
- **Server-side changes**: The user's issue might be on the service side (iLink, Telegram, etc.) and no client-side code change can fix it. Be honest about this.
- **Rate-limit error messages can be misleading**: `ret=-2` in iLink can mean either rate-limit OR stale session. Differentiate by checking the `errmsg` field.

## Verification

After completing the analysis:
1. State clearly whether the release addresses the issue
2. If it does NOT, explain what change would be needed (and whether that's a code change, config tunable, or upstream issue)
3. List any config tunables the user can adjust immediately to mitigate the issue
4. Provide the exact evidence (commit hash, log lines, code reference) for each claim
