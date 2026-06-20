---
name: github-connectivity-diagnosis
description: "Diagnose why git/GitHub operations fail (push, pull, clone, hermes update). Covers proxy residuals, HTTPS blocking, SSH fallback, and China-network workarounds."
version: 1.0.0
author: Hermes Agent
tags: [github, connectivity, proxy, ssh, network, china, troubleshooting]
---

# GitHub Connectivity Diagnosis

Diagnose and fix GitHub connectivity failures — `hermes update` hangs, `git push/pull` times out, `gh` can't authenticate, etc.

## Trigger Conditions

Use this skill when any git/GitHub operation fails with:
- `Failed to connect to 127.0.0.1 port XXXX` (stale proxy)
- `Couldn't connect to server`
- `Connection timed out` — especially for HTTPS (443)
- `unable to access 'https://github.com/...'`
- `Permission denied (publickey)` when SSH was expected to work
- Generic network errors on GitHub operations

## Step 1: Check Git Proxy Config

Git can have proxy set at three levels — check all:

```bash
# Local (repo-level) proxy
cd /path/to/repo
git config --local --get http.proxy
git config --local --get https.proxy

# Global (user-level) proxy
git config --global --get http.proxy
git config --global --get https.proxy

# System-level proxy
git config --system --get http.proxy
```

Additionally, `hermes update` runs via git internally, so its failure often traces to git proxy.

### Fix: Clear stale proxy

```bash
git config --global --unset http.proxy
git config --global --unset https.proxy
# Also local if set
git config --unset http.proxy
git config --unset https.proxy
```

## Step 2: Check Environment Variables

Shell env vars override or supplement git proxy config:

```bash
echo "http_proxy=$http_proxy"
echo "https_proxy=$https_proxy"
echo "HTTP_PROXY=$HTTP_PROXY"
echo "HTTPS_PROXY=$HTTPS_PROXY"
echo "ALL_PROXY=$ALL_PROXY"
echo "no_proxy=$no_proxy"
```

If any set to a stale proxy, unset them or fix in `~/.zshrc` / `~/.bashrc`.

## Step 3: Test GitHub Connectivity

Test each protocol independently to isolate the blockage:

```bash
# 1. ICMP (ping) — tests basic network path
ping -c 2 -t 5 github.com

# 2. HTTPS (443) — the default git protocol
curl -m 10 -s -o /dev/null -w "%{http_code}" https://github.com

# 3. API endpoint (often on a different CDN)
curl -m 10 -s -o /dev/null -w "%{http_code}" https://api.github.com

# 4. Raw content CDN
curl -m 10 -s -o /dev/null -w "%{http_code}" https://raw.githubusercontent.com

# 5. SSH transport
ssh -T -o ConnectTimeout=10 git@github.com
# Expected: "Permission denied (publickey)." — means TCP+SSH works, just no key
# Unexpected: "Connection timed out" — SSH is also blocked
```

### Interpretation Matrix

| ping | HTTPS | SSH | API | Likely Cause |
|------|-------|-----|-----|--------------|
| ✅ | ❌ | ✅ | ✅ | HTTPS blocked (common in China); use SSH |
| ✅ | ❌ | ❌ | ✅ | Deep packet inspection; need VPN/proxy |
| ✅ | ❌ | ❌ | ❌ | Full GitHub blocking; need VPN/proxy |
| ❌ | ❌ | ❌ | ❌ | No internet at all |
| ✅ | ✅ | ❌ | ✅ | SSH specifically blocked |
| ✅ | ✅ | ✅ | ✅ | Proxy config issue (see Step 1/2) |

## Step 4: Apply Fix

### Fix A — Switch to SSH (use when SSH works but HTTPS is blocked)

1. Generate an SSH key (if none exists):
   ```bash
   ssh-keygen -t ed25519 -C "your-email@example.com"
   cat ~/.ssh/id_ed25519.pub
   ```
2. Add public key to GitHub: Settings → SSH and GPG keys → New SSH key
3. Change remote URL:
   ```bash
   git remote set-url origin git@github.com:user/repo.git
   ```

### Fix B — Configure a working proxy (use when VPN/proxy is available)

```bash
git config --global http.proxy http://127.0.0.1:PORT
git config --global https.proxy http://127.0.0.1:PORT
```

Common proxy ports: 7890 (Clash), 1080/1087 (Shadowsocks), 8118 (Privoxy)

### Fix C — Use mirror proxy (temporary workaround when HTTPS is blocked)

```bash
git config --global url."https://ghproxy.com/https://github.com/".insteadOf https://github.com/
```

Note: mirror proxies are unreliable and may be blocked themselves. Treat as temporary.

## Pitfalls

- **Local vs global git config**: `hermes update` uses the repo's own git, but the proxy is often set at global level. Always check both.
- **SSH key check before assuming SSH works**: `ssh -T git@github.com` returning "Permission denied (publickey)" means SSH WORKS (TCP+SSH handshake succeeded) — the error is just about auth, not connectivity. Don't confuse this with a connectivity failure.
- **gh CLI**: The `gh` CLI may use a different auth path (OAuth token) and might work even when git HTTPS doesn't. Check with `gh auth status`.
- **'hermes update' timeout**: The built-in `hermes update` command has a short timeout (~15-20s). If GitHub is slow (not blocked), try direct `git pull --ff-only` inside `~/.hermes/hermes-agent/` with a longer timeout.
