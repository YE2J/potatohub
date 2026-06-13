---
name: karing-proxy
description: "Use when GitHub, Google, or other external sites are slow/ inaccessible. Opens Karing.app and toggles the proxy connection (red → green button)."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [proxy, network, github, karing, vpn, connectivity]
    related_skills: []
---

# Karing Proxy — Quick Connect

## Overview

Karing (`/Applications/Karing.app`) is a proxy/VPN tool on macOS that routes traffic through a faster path. When GitHub, Google, or other external sites are slow or unreachable, open Karing and activate the connection by clicking the red logo at the bottom of the app window.

## When to Use

- `git push/clone/fetch` hangs or times out
- `web_search` or `web_extract` on GitHub / Google / external sites returns errors or times out
- Any HTTP/HTTPS request to foreign domains is noticeably slow
- User says "use the proxy" or "open karing/karen/karin" (remember: the actual app is **Karing**)
- General "外网访问慢" (slow external access)

## How to Connect

### Step 1: Open Karing's window
Karing is a **menu bar app** (no dock icon, just a menubar icon). Use the URL scheme to pop open its window:

```shell
open "karing://"
```

This opens a floating panel window. If Karing isn't running at all, start it first:
```shell
open /Applications/Karing.app
sleep 2
open "karing://"
```

### Step 2: Wait for the window to appear
Give it 1-2 seconds to render, then use cua-driver to capture the window state:

```shell
cua-driver call list_windows '{}'
# Find Karing's PID and window_id, then:
cua-driver call get_window_state '{"pid": <PID>, "window_id": <WINDOW_ID>}'
```

### Step 3: Locate the connection button
The app has a large **circular shield icon** at the **bottom center** of its window. This is the connect/disconnect toggle.

- **White shield + green checkmark** ✅ = connected (proxy active)
- **Red shield** 🔴 = disconnected (no proxy)
- **System Proxy toggle** in the UI should also be green when active

### Step 4: Click the connection button
Use cua-driver to click the shield button. Find its element index in the AX tree first (usually near the bottom of the tree), then:

```shell
cua-driver call click '{"pid": <PID>, "window_id": <WINDOW_ID>, "element_index": <N>}'
```

### Step 5: Verify the connection turned green
Re-capture the window state and check the shield icon changed from red to green. If still red, try clicking again.

### Quick check: is the proxy already connected?
```shell
curl -s -o /dev/null -w "%{http_code} %{time_total}s" https://github.com
```
Or check your current IP:
```shell
curl -s --max-time 5 https://ipinfo.io/ip
```
- If GitHub returns 200 in under 1s and the IP is non-Chinese, the proxy is working.
- Karing often remembers its last state, so it may already be connected when you open it.

## Verifying the Connection

After connecting, verify that GitHub / external sites are reachable:

```shell
curl -s -o /dev/null -w "%{http_code} %{time_total}s" https://github.com
```

Should return `200` with a reasonable time (under 5s).

Or ping a blocked site:
```shell
curl -s -o /dev/null -w "%{http_code}" https://www.google.com
```

## Disconnecting (when done)

If the user later reports "download is done, close the proxy" or similar:
1. Open Karing again: `open /Applications/Karing.app`
2. Click the **green** logo at the bottom to turn it red (disconnected)

## Common Pitfalls

1. **The app name is "Karing", not "Karin" or "Karen".** macOS uses `/Applications/Karing.app`. Don't try `karin`, `karing.app` (lowercase) will fail.
2. **Karing may already be running.** `open` command is safe — it brings the window to front.
3. **Button position shifts with window size.** If the first click misses, try resizing or using vision-based clicking with CUA.
4. **If already green**, no need to click — it's already connected. Skip to verification.
5. **If clicking the button doesn't change the color**, the proxy config may be invalid. Tell the user.
6. **Some networks (corporate WiFi, hotel networks) block proxy protocols.** If connection fails, warn the user.
7. **Don't leave it on unnecessarily.** Proxies can slow down local/CDN traffic. Disconnect after the slow-access task is done.

## Verification Checklist

- [ ] Karing app opens successfully
- [ ] Connection logo turns from red to green
- [ ] `curl https://github.com` returns 200 within a reasonable time
- [ ] Proceed with the original task (git clone, web search, etc.)
- [ ] Disconnect Karing when the task is complete (green → red)
