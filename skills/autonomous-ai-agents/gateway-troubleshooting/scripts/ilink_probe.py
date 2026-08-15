#!/usr/bin/env python3
"""iLink channel probe — diagnose Weixin send failures from the CLI.

Usage: python3 ilink_probe.py [account_file]

Reads the newest account file under ~/.hermes/weixin/accounts/*@im.bot.json
(or the given path), then probes three endpoints with the CORRECT envelope
(see gateway/platforms/weixin.py _headers() + _base_info()):

  1. getconfig   — token/account validity. ret=0 means token is valid, bot online.
  2. sendmessage — the REAL send path:
       ret=-2 "prepare failed"     = server rejects sends (stale context_token /
                                     account-level block) — NOT a 30s cooldown
       errcode=-14 "session timeout" = context_token/session expired
  3. getupdates  — long-poll reachability (8s timeout; empty/timeout is normal,
                    a msgs[] array means inbound channel alive).

NOTE: sendmessage delivers a real test message to the user's WeChat.
Headers MUST match the adapter exactly or the server returns ret=-1 "invalid request":
  Authorization: Bearer <token>, AuthorizationType: ilink_bot_token,
  iLink-App-Id: bot, iLink-App-ClientVersion: (2<<16)|(2<<8)|0,
  X-WECHAT-UIN: random, body includes base_info {"channel_version": "2.2.0"}.
"""
import json
import os
import random
import sys
import urllib.request
import urllib.error
import glob

ACCT_DIR = os.path.expanduser("~/.hermes/weixin/accounts")


def load_account(path):
    with open(path) as f:
        return json.load(f)


def call(base_url, token, user_id, endpoint, payload, timeout=15):
    url = f"{base_url.rstrip('/')}/ilink/bot/{endpoint}"
    body = json.dumps(
        {"base_info": {"channel_version": "2.2.0"}, **payload},
        ensure_ascii=False, separators=(",", ":"),
    ).encode()
    headers = {
        "Content-Type": "application/json",
        "AuthorizationType": "ilink_bot_token",
        "Content-Length": str(len(body)),
        "X-WECHAT-UIN": str(random.randint(0, 2 ** 31 - 1)),
        "iLink-App-Id": "bot",
        "iLink-App-ClientVersion": str((2 << 16) | (2 << 8) | 0),
        "Authorization": f"Bearer {token}",
    }
    req = urllib.request.Request(url, data=body, headers=headers)
    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
        return f"HTTP {resp.status}: {resp.read().decode()[:300]}"
    except urllib.error.HTTPError as e:
        return f"HTTPError {e.code}: {e.read().decode()[:300]}"
    except Exception as e:
        return f"ERR: {type(e).__name__} {str(e)[:200]}"


def main():
    acct_path = sys.argv[1] if len(sys.argv) > 1 else None
    if not acct_path:
        files = sorted(
            glob.glob(os.path.join(ACCT_DIR, "*@im.bot.json")),
            key=os.path.getmtime, reverse=True,
        )
        if not files:
            print("no account files found under", ACCT_DIR)
            return 1
        acct_path = files[0]
    acct = load_account(acct_path)
    token = acct.get("token", "")
    base = acct.get("base_url", "https://ilinkai.weixin.qq.com")
    uid = acct.get("user_id", "")
    print(f"account: {os.path.basename(acct_path)}  user: {uid[:20]}...")
    print("getconfig :", call(base, token, uid, "getconfig", {"ilink_user_id": uid}))
    msg = {
        "msg": {
            "from_user_id": "", "to_user_id": uid,
            "client_id": "probe-" + str(random.randint(100000, 999999)),
            "message_type": 2, "message_state": 2,
            "item_list": [{"type": 1, "text_item": {"text": "🔍 iLink probe"}}],
        }
    }
    print("sendmessage:", call(base, token, uid, "sendmessage", msg))
    print("getupdates :", call(
        base, token, uid, "getupdates",
        {"ilink_user_id": uid, "client_id": "probe-" + str(random.randint(1000, 9999))},
        timeout=8,
    ))
    return 0


if __name__ == "__main__":
    sys.exit(main())
