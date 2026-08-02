#!/bin/bash
# =========================================================
# dns_harden.sh — DNS 缓存加固 v1.0
# Cron: "0 0 * * *", no_agent=true, deliver=local
# Pre-caches DNS records for key services. When real-time
# DNS fails (common in macOS launchd environments), the
# ilink_health.sh script falls back to these cached IPs.
# =========================================================
set -u

CACHE_DIR="$HOME/.hermes/health_shared"
mkdir -p "$CACHE_DIR"

SERVICES=(
  "ilinkai.weixin.qq.com"
  "api.openai.com"
  "api.deepseek.com"
)

UPDATED=0; FAILED=0

for HOST in "${SERVICES[@]}"; do
  CACHE_FILE="$CACHE_DIR/$(echo "$HOST" | tr '.' '_')_dns_cache.txt"
  DIG_IPS=$(dig +short "$HOST" 2>/dev/null | grep -E "^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$")
  if [ -n "$DIG_IPS" ]; then
    echo "$DIG_IPS" > "$CACHE_FILE"
    echo "✅ $HOST → $(echo $DIG_IPS | tr '\n' ' ')"
    UPDATED=$((UPDATED + 1))
  elif [ -f "$CACHE_FILE" ]; then
    echo "⚠️ $HOST resolution failed, keeping cache"
    FAILED=$((FAILED + 1))
  else
    echo "❌ $HOST resolution failed, no cache available"
    FAILED=$((FAILED + 1))
  fi
done

echo ""
echo "DNS cache: $UPDATED updated, $FAILED failed"
