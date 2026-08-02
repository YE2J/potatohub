#!/bin/bash
# =========================================================
# delivery_retry.sh — 晨报补推脚本 v1.0
# Scans pending/ queue, retries delivery with exponential backoff.
# Cron usage: no_agent=true, deliver=origin (WeChat home channel)
# Suppressed output → [SILENT] = no push attempt.
# =========================================================
set -u

PENDING_DIR="$HOME/.hermes/delivery/pending"
mkdir -p "$PENDING_DIR"

# Find oldest undelivered report (FIFO)
LATEST_PENDING=$(find "$PENDING_DIR" -maxdepth 1 -name "*_晨报.md" -print0 | sort -z | head -1)

if [ -z "$LATEST_PENDING" ]; then
  echo "[SILENT]"
  exit 0
fi

BASENAME=$(basename "$LATEST_PENDING" .md)

# Pre-flight health check
timeout 3 bash -c "echo > /dev/tcp/ilinkai.weixin.qq.com/443" 2>/dev/null
if [ $? -ne 0 ]; then
  echo "[SILENT]"
  exit 0
fi

# Exponential backoff check
RETRIES=$(cat "$PENDING_DIR/${BASENAME}.retry_count" 2>/dev/null || echo "0")
FIRST_ATTEMPT=$(cat "$PENDING_DIR/${BASENAME}.first_attempt" 2>/dev/null || echo "0")
NOW_SEC=$(date +%s)

case "$RETRIES" in
  0) MIN_INTERVAL=0      ;;
  1) MIN_INTERVAL=1800   ;;
  2) MIN_INTERVAL=3600   ;;
  *) MIN_INTERVAL=7200   ;;
esac

ELAPSED=$((NOW_SEC - FIRST_ATTEMPT))

if [ "$RETRIES" -ge 3 ]; then
  mv "$LATEST_PENDING" "$PENDING_DIR/${BASENAME}.abandoned"
  echo "[SILENT]"
  exit 0
fi

if [ "$RETRIES" -ge 1 ] && [ "$ELAPSED" -lt "$MIN_INTERVAL" ]; then
  echo "[SILENT]"
  exit 0
fi

# Deliver
RETRY_IDX=$((RETRIES + 1))
echo "📋 晨报补推 (第${RETRY_IDX}次)"
echo ""
cat "$LATEST_PENDING"

echo "$RETRY_IDX" > "$PENDING_DIR/${BASENAME}.retry_count"
[ "$RETRIES" -eq 0 ] && echo "$(date +%s)" > "$PENDING_DIR/${BASENAME}.first_attempt"
