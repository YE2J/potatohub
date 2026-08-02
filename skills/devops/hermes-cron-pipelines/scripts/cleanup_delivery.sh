#!/bin/bash
# =========================================================
# cleanup_delivery.sh — 晨报交付队列清理 v1.0
# Cron: "0 12 * * *", no_agent=true, deliver=local
# Maintains the pending/ queue: expire old delivered/abandoned
# markers, count abandoned reports, alert if ≥3 in 7 days.
# =========================================================
set -u

PENDING_DIR="$HOME/.hermes/delivery/pending"
mkdir -p "$PENDING_DIR"

PENDING_COUNT=$(find "$PENDING_DIR" -maxdepth 1 -name "*_晨报.md" ! -name "*.delivered" ! -name "*.abandoned" | wc -l | tr -d ' ')
DELIVERED_COUNT=$(find "$PENDING_DIR" -maxdepth 1 -name "*.delivered" | wc -l | tr -d ' ')
ABANDONED_COUNT=$(find "$PENDING_DIR" -maxdepth 1 -name "*.abandoned" | wc -l | tr -d ' ')

echo "📋 Delivery Queue — $(date '+%Y-%m-%d %H:%M')"
echo "  Pending: $PENDING_COUNT | Delivered: $DELIVERED_COUNT | Abandoned: $ABANDONED_COUNT"

# Expire old markers (7 days)
find "$PENDING_DIR" -maxdepth 1 \( -name "*.delivered" -o -name "*.abandoned" \) -mtime +7 -delete 2>/dev/null
find "$PENDING_DIR" -maxdepth 1 \( -name "*.retry_count" -o -name "*.first_attempt" \) -mtime +3 -delete 2>/dev/null

# Alert: ≥3 abandoned reports in last 7 days
SEVERE=$(find "$PENDING_DIR" -maxdepth 1 -name "*.abandoned" -mtime -7 | wc -l | tr -d ' ')
if [ "$SEVERE" -ge 3 ]; then
  echo ""
  echo "🔴 ALERT: $SEVERE reports abandoned in 7 days — check iLink channel"
fi

echo "✅ Cleanup done"
