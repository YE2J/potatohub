# Cron Delivery Failure — Diagnosis Checklist (case: 2026-08-09 morning report)

Symptom: user reports the 07:05 morning report never arrived on WeChat.
Cron job list shows `last_status: ok` — but ok ≠ delivered.

## Diagnosis order

1. `cronjob action=list` → find the job, read `last_delivery_error`.
   `last_status: ok` = script exit 0 only. (Here: "Weixin send failed: iLink
   sendmessage rate limited; cooldown active for 30.0s" — delivery failed.)
2. Content is NOT lost: `~/.hermes/cron/output/<job_id>/<YYYY-MM-DD_HH-MM-SS>.md`
   holds the full generated report even when delivery fails. Re-push manually:
   `grep -v '^\[CRON_LOG\]' <file> > /tmp/report.md && hermes send --to weixin:<id> --file /tmp/report.md`
   (strip the `[CRON_LOG]` wrapper lines first).
3. `cron_push_log` (stock_data.db): `delivery_status=n/a` for no_agent jobs —
   it records SCRIPT execution (exit code), NOT delivery outcome. A `success`
   row does NOT mean the message was delivered. Cross-check gateway.error.log /
   gateway.log `[Weixin] send failed` lines instead.
4. `~/.hermes/logs/morning_report_v7.log` — the v7 shell wrapper appends script
   stdout + exit here. Confirms the generation side (report text + exit=0).

## Pitfalls found (2026-08-09)

- **delivery_retry.sh exists but is NOT registered as a cron job:**
  `~/.hermes/scripts/delivery_retry.sh` (v1.2) scans `~/.hermes/delivery/pending/`
  for `*_晨报.md` and retries with backoff, but (a) no cron job runs it
  (cleanup_delivery.sh 12:00 is the only delivery-related cron), and (b) v7
  scripts emit stdout and never write the pending queue (stale 07-02/07-03
  files are v5-era leftovers). Net effect: when delivery fails there is NO
  automatic retry — content just sits in the output dir. To fix: register
  delivery_retry (08:00/09:00) AND make v7 write the report into pending/, or
  accept manual re-push from the output dir.
- **gateway.error.log lines have NO timestamps** — correlate line ranges with
  gateway.log timestamps to reconstruct timelines.
- **ilink_health.sh can report "✅ healthy" while sends are rejected** — it only
  tests DNS + TCP, never the sendmessage endpoint (8/9 it exited 0 while every
  send failed). Use it for connectivity, not capability.

## Downstream diagnosis

When the delivery failure is server-side (iLink ret=-2 / errcode=-14), hand off
to the gateway-troubleshooting skill → `references/ilink-rate-limit-rebind.md`
(direct API probe + QR rebind workflow).
