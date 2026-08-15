# iLink Sustained "rate limited" — Server-Side Rejection & QR Rebind

Case: 2026-08-09 — morning report + all WeChat pushes failed for 40+ hours with
`Weixin send failed: iLink sendmessage rate limited; cooldown active for 30.0s`.

## The key distinction: local circuit breaker vs server rejection

- The adapter has a LOCAL circuit breaker: `WEIXIN_RATE_LIMIT_CIRCUIT_THRESHOLD`
  (default 1), window 30s, open 30s (weixin.py `_rate_limit_circuit_*`).
  "cooldown active for 30.0s" is LOCAL bookkeeping and only lasts 30s.
- If failures persist beyond 30s, across gateway restarts, for hours → the
  iLink SERVER is rejecting (ret=-2). **Gateway restart does NOT fix it**
  (verified: 8/8 13:33 restart, still failing 8/9 07:05).

## Probe the API directly (bypass local state)

Saved accounts: `~/.hermes/weixin/accounts/<account_id>@im.bot.json`
fields: `token`, `base_url` (default https://ilinkai.weixin.qq.com), `user_id`.

Constants (weixin.py): ILINK_APP_ID="bot", CHANNEL_VERSION="2.2.0",
ILINK_APP_CLIENT_VERSION=(2<<16)|(2<<8)|0 = 131584,
EP_SEND_MESSAGE="ilink/bot/sendmessage".

Request format must match exactly (wrong shape → ret=-1 "invalid request"):
- sendmessage body:
  `{"msg": {"from_user_id":"","to_user_id":USER,"client_id":"...","message_type":2,"message_state":2,"item_list":[{"type":1,"text_item":{"text":"..."}}]}, "base_info":{"channel_version":"2.2.0"}}`
- headers: `Authorization: Bearer <token>`, `AuthorizationType: ilink_bot_token`,
  `iLink-App-Id: bot`, `iLink-App-ClientVersion: 131584`,
  `X-WECHAT-UIN: <random 31-bit int>`
- getconfig body: `{"ilink_user_id": USER, "base_info": {...}}`

## Response code table

| Code | Meaning | Action |
|------|---------|--------|
| ret=0 | OK | — |
| ret=-2 / errmsg "prepare failed" | Server refuses to send (sustained) | rebind QR or wait |
| errcode=-14 "session timeout" | Token session expired | rebind QR |
| ret=-1 "invalid request" | Wrong request format | fix format, not a server problem |
| getupdates timeout | Long-poll by design (35s) | timeout ≠ error |

Key probe pattern: getconfig ret=0 while sendmessage ret=-2 ⇒ token VALID but
server still refuses sends. Backup accounts may all be session-timeout (-14).

## Rebind workflow (hermes gateway setup)

IMPORTANT: this CLI is interactive — run it in a background PTY process
(`background=true, pty=true`). Piping stdout (`... | head`) kills the process.

1. `hermes gateway setup` (background PTY)
2. Numbered menu: select platform by number (Weixin = 3), then
   "Reconfigure Weixin? [y/N]" → y, "Start QR login now? [Y/n]" → y
3. Output shows BOTH an ASCII QR and a scan URL
   `https://liteapp.weixin.qq.com/q/<id>?qrcode=<hex>&bot_type=3`
4. Give the user the URL AND a scannable PNG (ASCII QR in a background process
   is not visible to the user):
   `python3 -c "import qrcode; qrcode.make('<url>').save('/tmp/weixin_rebind_qr.png')"`
   then deliver with `MEDIA:/tmp/weixin_rebind_qr.png`. Scan promptly (QR is time-limited).
5. On success Hermes writes the new token to `~/.hermes/.env` + account JSON;
   gateway picks it up (may need `hermes gateway restart`).

## History / self-recovery

6/12 had multi-hour iLink rate limiting that self-recovered the same day. A
sustained (40h+) rejection is unusual — QR rebind is the reliable recovery
path, but wait-and-retry (`hermes send`) is a valid option if the user prefers.
Do NOT claim rebind fixed the channel until a send actually succeeds.
