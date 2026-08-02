#!/bin/bash
# =========================================================
# ilink_health.sh — iLink 推送通道健康检查 v1.0
# Used by: delivery_retry.sh, daily_morning_report_v4.sh
# Returns: 0=healthy, 1=DNS failure, 2=TCP failure, 3=rate-limited recently
# =========================================================
set -u

HOST="ilinkai.weixin.qq.com"
PORT=443
CACHE_DIR="$HOME/.hermes/health_shared"
mkdir -p "$CACHE_DIR"
CACHE_FILE="$CACHE_DIR/ilink_last_ok_ip"
DNS_CACHE="$CACHE_DIR/ilink_dns_cache.txt"

# (1) DNS resolution — try realtime first, fall back to cache
DNS_IPS=$(dig +short "$HOST" 2>/dev/null | grep -E "^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$")
if [ -z "$DNS_IPS" ]; then
  if [ -f "$DNS_CACHE" ]; then
    DNS_IPS=$(cat "$DNS_CACHE")
    echo "⚠️ DNS fallback" >&2
  elif [ -f "$CACHE_FILE" ]; then
    DNS_IPS=$(cat "$CACHE_FILE")
    echo "⚠️ DNS fallback (last IP)" >&2
  else
    echo "❌ DNS failure, no cache" >&2
    exit 1
  fi
else
  echo "$DNS_IPS" > "$DNS_CACHE"
fi

# (2) TCP connectivity — try each resolved IP
TCP_OK=false
for IP in $DNS_IPS; do
  if timeout 3 bash -c "echo > /dev/tcp/$IP/$PORT" 2>/dev/null; then
    echo "$IP" > "$CACHE_FILE"
    TCP_OK=true
    break
  fi
done

if [ "$TCP_OK" = false ]; then
  echo "❌ TCP failure: $HOST:$PORT" >&2
  exit 2
fi

# (3) Recent rate-limit check
LOG_FILE="$HOME/.hermes/logs/gateway.error.log"
if [ -f "$LOG_FILE" ]; then
  RECENT=$(grep "send failed.*rate limited" "$LOG_FILE" 2>/dev/null | tail -1)
  if [ -n "$RECENT" ]; then
    LOG_TIME=$(echo "$RECENT" | grep -oE "^[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}")
    if [ -n "$LOG_TIME" ]; then
      LOG_EPOCH=$(date -j -f "%Y-%m-%d %H:%M:%S" "$LOG_TIME" +%s 2>/dev/null)
      NOW_EPOCH=$(date +%s)
      if [ $((NOW_EPOCH - LOG_EPOCH)) -lt 600 ]; then
        echo "⚠️ Rate-limited $((NOW_EPOCH - LOG_EPOCH))s ago" >&2
        exit 3
      fi
    fi
  fi
fi

echo "✅ Healthy" >&2
echo "${DNS_IPS%% *}"
exit 0
