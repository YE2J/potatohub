---
name: gateway-troubleshooting
description: "Diagnose and fix Hermes messaging gateway connectivity issues — platform startup failures, crash loops, env var recovery, and token restoration."
version: 1.0.0
author: Hermes Agent
metadata:
  hermes:
    tags: [hermes, gateway, weixin, wechat, troubleshooting, crash-loop, platform]
---

# Gateway Troubleshooting

Diagnose and fix issues where a Hermes messaging platform (Weixin, Telegram, Discord, etc.) is not connecting or receiving/sending messages.

## Quick Check

```bash
# 1. Is gateway running?
hermes gateway status

# 2. Any platform connected?
hermes gateway status --all
# or in-session: /platforms or /gateway

# 3. Check logs for errors
grep -i "error\|fail\|crash\|weixin\|disconnect" ~/.hermes/logs/gateway.log | tail -20
```

## Common Failure Patterns

### Pattern 1: "No messaging platforms enabled"

**Symptom:** Gateway starts but says "No messaging platforms enabled."
**Log:** `WARNING gateway.run: No messaging platforms enabled.`

**Fix:**
```bash
# Check if platform is disabled in config
grep -A3 "platforms:" ~/.hermes/config.yaml | grep -E "enabled:|weixin:|telegram:"

# Enable (example for weixin)
hermes config set platforms.weixin.enabled true

# Restart gateway
hermes gateway restart
```

### Pattern 2: Platform fails with "XXX_TOKEN is required"

**Symptom:** Gateway detects the platform but can't authenticate.
**Log:** `WARNING: [Weixin] Weixin startup failed: WEIXIN_TOKEN is required`

**Fix:** Token env var missing from `.env`. Check if saved token still exists on disk:

```bash
# Check saved token files (Weixin example)
ls ~/.hermes/weixin/accounts/

# Read the token (account_id and token are in the JSON)
cat ~/.hermes/weixin/accounts/*@im.bot.json

# Add missing env vars to .env
echo 'WEIXIN_ACCOUNT_ID=your-account-id' >> ~/.hermes/.env
echo 'WEIXIN_TOKEN=your-token-string' >> ~/.hermes/.env
```

**Key insight:** The token files on disk survive gateway restarts and config changes. If the `.env` vars are missing but the JSON files are intact, **you do NOT need to re-scan QR code** — just restore the env vars from the JSON files.

### Pattern 3: "open policy without allow-all opt-in"

**Symptom:** Gateway reads the token correctly but refuses to start.
**Log:** `ERROR: refusing to start: weixin has dm_policy/group_policy set to 'open' but neither GATEWAY_ALLOW_ALL_USERS nor WEIXIN_ALLOW_ALL_USERS is enabled.`

**Fix:** The `open` DM policy requires an explicit safety opt-in:

```bash
echo 'WEIXIN_ALLOW_ALL_USERS=true' >> ~/.hermes/.env
# Or the global version:
echo 'GATEWAY_ALLOW_ALL_USERS=true' >> ~/.hermes/.env
```

### Pattern 4: Gateway crash-loop

**Symptom:** Gateway repeatedly starts and crashes. Process shows as "Sleep" or cycles.
**Log:** Repeated "Gateway exiting cleanly" followed by "Gateway Starting..."

**Cause:** A platform that fails to start with a **non-retryable** error causes the gateway to exit immediately. launchd (macOS) or systemd restarts it, starting the cycle.

**Fix:**
1. Unload the launchd service to stop auto-restarts:
   ```bash
   launchctl bootout gui/$(id -u)/ai.hermes.gateway
   ```
2. Fix the underlying issue (Pattern 1/2/3 above)
3. Reload the service:
   ```bash
   launchctl bootstrap gui/$(id -u) /Users/yellow/Library/LaunchAgents/ai.hermes.gateway.plist
   ```

Note: `hermes gateway restart` or `launchctl stop` may be **blocked** when running from inside a session connected to the gateway (SIGTERM propagates to the child process). Use `launchctl bootout` from a terminal within the Hermes app session — it bypasses this restriction.

### Pattern 5: Stale launchd service definition

**Symptom:** `hermes gateway status` shows:
```
⚠ Service definition is stale relative to the current Hermes install
  Run: hermes gateway start
```

**Fix:** The launchd plist points to an older Python/venv path. Reinstall the service:
```bash
hermes gateway start
```

### Pattern 6: Weixin sends fail with "iLink sendmessage rate limited" for hours/days

**Symptom:** All WeChat deliveries fail (cron `last_delivery_error` + manual `hermes send`), message: `iLink sendmessage rate limited; cooldown active for 30.0s`. May be preceded by DNS poll errors (`nodename nor servname provided`) hours earlier.

**Key distinction — local circuit breaker vs server-side rejection:** The adapter has a LOCAL 30s circuit breaker (`WEIXIN_RATE_LIMIT_CIRCUIT_*`, default threshold 1 / window 30s / open 30s). If failures persist past 30s, across gateway restarts, for hours → the **iLink server itself is rejecting** (ret=-2, errmsg "prepare failed"). Gateway restart does NOT fix this.

**Diagnose (see `references/ilink-rate-limit-rebind.md`):**
1. `hermes send --list` to confirm the target id
2. Probe iLink directly — fastest path: `python3 <skill_dir>/scripts/ilink_probe.py` (getconfig + sendmessage + getupdates with the exact adapter envelope). getconfig ret=0 (token valid) while sendmessage ret=-2 "prepare failed" → server refuses sends. Wrong request shape yields ret=-1 "invalid request" — distinguish format bugs from server rejection.
3. Check backup accounts `~/.hermes/weixin/accounts/*@im.bot.json` — likely session-timeout (errcode=-14).
4. Note: `ilink_health.sh` only tests DNS/TCP, can report healthy while sends are rejected.

**Recovery:** Wait (historically self-recovers within hours) or re-bind via QR — `hermes gateway setup` (interactive; run in background PTY, NOT piped through `| head`). See `references/ilink-rate-limit-rebind.md` for the full request format, response-code table, and QR rebind steps.

## General Recovery Workflow

When a platform stops working unexpectedly:

1. **Check gateway status** — `hermes gateway status`, `/platforms`
2. **Check recent logs** — `tail -30 ~/.hermes/logs/gateway.log`
3. **Verify platform is enabled** in `~/.hermes/config.yaml`
4. **Verify env vars** in `~/.hermes/.env` — check against known-good values
5. **Check saved credentials** on disk (platform-specific path)
6. **If all else fails**, re-run the setup wizard:
   ```bash
   hermes gateway setup
   ```

## Platform-Specific Recovery Paths

### Weixin (WeChat)

- Saved tokens: `~/.hermes/weixin/accounts/<account_id>@im.bot.json`
- Required env vars: `WEIXIN_ACCOUNT_ID`, `WEIXIN_TOKEN`
- Optional: `WEIXIN_DM_POLICY`, `WEIXIN_ALLOW_ALL_USERS`, `WEIXIN_HOME_CHANNEL`
- Approved users: `~/.hermes/pairing/weixin-approved.json`
- If QR login is needed: `hermes gateway setup` → select Weixin

See `skill_view(name="gateway-troubleshooting", file_path="references/weixin-recovery.md")` for a complete worked example.

### Other Platforms

- Telegram: token from BotFather → `TELEGRAM_BOT_TOKEN`
- Discord: bot token from Developer Portal → `DISCORD_BOT_TOKEN`
- Generic pattern: find saved credentials under `~/.hermes/<platform>/`, restore env vars from them

## Pitfalls

- **Do NOT `pkill -f "hermes_cli.main gateway"`** — this kills the entire gateway process tree. Use `launchctl bootout` on macOS for clean teardown.
- **Cannot restart gateway from within gateway session.** The SIGTERM propagates to the terminal command. Use `launchctl bootout/bootstrap` cycle instead.
- **Crash-loop with `KeepAlive: true`** in launchd plist can generate hundreds of log entries very quickly. Always `bootout` first, fix, then `bootstrap`.
- **.env file must be writable after appends.** Be careful not to add duplicate env vars — check with `grep WEIXIN ~/.hermes/.env` first.
- **Config tools (`hermes config set`) cannot set nested `platforms.X.extra` keys** for platform-specific extra config. Use direct `.env` edits or `patch` the config.yaml.
