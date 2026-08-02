# Weixin Recovery — Worked Example

This reference documents a real recovery session where the Weixin (WeChat) messaging platform stopped communicating with Hermes.

## Incident Timeline

1. Gateway received an unexpected signal at **00:51** and restarted
2. On restart, `weixin.enabled` was `false` in config.yaml → "No messaging platforms enabled"
3. Enabling it revealed `WEIXIN_TOKEN` was missing from `.env`
4. After restoring token, the gateway then hit safety gate: "open policy without allow-all opt-in"
5. After adding `WEIXIN_ALLOW_ALL_USERS=true`, Weixin connected successfully

## Root Cause Chain

```
Gateway unexpected restart
  → config.yaml had weixin: enabled: false (unknown cause)
  → .env had no WEIXIN_ACCOUNT_ID or WEIXIN_TOKEN (lost during earlier config change)
  → Weixin token files still existed on disk (they don't get deleted)
```

## Step-by-Step Recovery

### Step 1: Verify the symptom

```bash
hermes gateway status
# → ⚠ Service definition is stale
# → ✓ Gateway is supervised by launchd (PID ...)
```

Check logs:

```bash
grep "weixin\|No messaging" ~/.hermes/logs/gateway.log | tail -10
```

### Step 2: Check platform config

```bash
grep -A3 "platforms:" ~/.hermes/config.yaml
# → platforms:
# →   qqbot:
# →     enabled: false
# →   weixin:
# →     enabled: false   ← PROBLEM
```

**Fix:**
```bash
hermes config set platforms.weixin.enabled true
```

### Step 3: Check env vars

```bash
grep WEIXIN ~/.hermes/.env
# → (empty)  ← PROBLEM
```

**Fix — find the saved token:**

```bash
ls ~/.hermes/weixin/accounts/
# → 7e0644718279@im.bot.json  (plus context-tokens, sync files)

cat ~/.hermes/weixin/accounts/7e0644718279@im.bot.json
# → {
# →   "token": "7e0644718279@im.bot:060000c881e34380824a10cf21036ea834ce01",
# →   "base_url": "https://ilinkai.weixin.qq.com",
# →   "user_id": "o9cq805uZu7aoWMYhFOBa48LxEBQ@im.wechat",
# →   "saved_at": "2026-07-07T23:59:54Z"
# → }
```

Restore env vars:

```bash
cat >> ~/.hermes/.env << 'EOF'
WEIXIN_ACCOUNT_ID=7e0644718279@im.bot
WEIXIN_TOKEN=7e0644718279@im.bot:060000c881e34380824a10cf21036ea834ce01
WEIXIN_DM_POLICY=open
WEIXIN_HOME_CHANNEL=o9cq805uZu7aoWMYhFOBa48LxEBQ@im.wechat
WEIXIN_HOME_CHANNEL_NAME=Home
EOF
```

### Step 4: Handle safety gate

```bash
echo 'WEIXIN_ALLOW_ALL_USERS=true' >> ~/.hermes/.env
# OR in config: set WEIXIN_DM_POLICY=allowlist + WEIXIN_ALLOWED_USERS=list
```

### Step 5: Restart the gateway

Since you're inside the Hermes Desktop app (can't `hermes gateway restart` from inside):

```bash
# Stop the crash-loop
launchctl bootout gui/$(id -u)/ai.hermes.gateway

# Start fresh
launchctl bootstrap gui/$(id -u) /Users/yellow/Library/LaunchAgents/ai.hermes.gateway.plist

# Verify
sleep 5 && tail -5 ~/.hermes/logs/gateway.log
# → ✓ weixin connected
# → Gateway running with 1 platform(s)
```

## Key Files Reference

| File | Purpose |
|------|---------|
| `~/.hermes/config.yaml` → `platforms.weixin.enabled` | Toggle platform on/off |
| `~/.hermes/.env` → `WEIXIN_ACCOUNT_ID`, `WEIXIN_TOKEN` | Platform auth credentials |
| `~/.hermes/weixin/accounts/*.json` | **Durable token store** — survives env var loss |
| `~/.hermes/weixin/accounts/*.context-tokens.json` | Per-user context tokens for reply continuity |
| `~/.hermes/weixin/accounts/*.sync.json` | Long-poll sync cursor (resume position) |
| `~/.hermes/pairing/weixin-approved.json` | Approved user IDs |
| `~/.hermes/logs/gateway.log` | Gateway runtime log |
| `~/Library/LaunchAgents/ai.hermes.gateway.plist` | macOS launchd service definition |

## Prevention

To avoid this happening again:

1. **Backup `.env` regularly** — it only contains API keys and platform tokens
2. **The token files in `~/.hermes/weixin/accounts/` are durable** — if they exist, you can always recover without re-scanning QR
3. **After any `hermes config edit` or config migration**, verify:
   ```bash
   grep -A2 "weixin" ~/.hermes/config.yaml  # enabled: true?
   grep WEIXIN ~/.hermes/.env                # all env vars present?
   ```

## Env Vars Summary

| Variable | Required | Notes |
|----------|----------|-------|
| `WEIXIN_ACCOUNT_ID` | ✅ | From the `.json` file's account ID |
| `WEIXIN_TOKEN` | ✅ | From the `.json` file's token field |
| `WEIXIN_DM_POLICY` | ❌ (default: open) | Must match `WEIXIN_ALLOW_ALL_USERS` setting |
| `WEIXIN_ALLOW_ALL_USERS` | when dm_policy=open | Safety gate |
| `WEIXIN_HOME_CHANNEL` | ❌ | For cron/notification delivery |
| `WEIXIN_HOME_CHANNEL_NAME` | ❌ | Display name |
