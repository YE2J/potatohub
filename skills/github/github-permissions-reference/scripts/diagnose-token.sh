#!/bin/bash
# diagnose-token.sh — Check a GitHub token's validity and permissions
# Usage: GITHUB_TOKEN=<token> bash diagnose-token.sh
# Or:   bash diagnose-token.sh <token>

set -e

TOKEN="${1:-$GITHUB_TOKEN}"
if [ -z "$TOKEN" ]; then
  echo "❌ No token provided. Set GITHUB_TOKEN env var or pass as arg."
  exit 1
fi

echo "=== GitHub Token Diagnostics ==="
echo ""

# 1. Validate token
echo "--- Step 1: Token Validity ---"
USER_RESP=$(curl -s -w "\n%{http_code}" -H "Authorization: token $TOKEN" https://api.github.com/user)
HTTP_CODE=$(echo "$USER_RESP" | tail -1)
USER_DATA=$(echo "$USER_RESP" | sed '$d')

if [ "$HTTP_CODE" != "200" ]; then
  ERROR_MSG=$(echo "$USER_DATA" | python3 -c "import sys,json; print(json.load(sys.stdin).get('message','unknown'))" 2>/dev/null)
  echo "❌ Token INVALID: HTTP $HTTP_CODE — $ERROR_MSG"
  echo ""
  echo "Possible causes:"
  echo "  - Token expired or revoked"
  echo "  - Token was pasted but redacted by security system"
  exit 1
fi

USERNAME=$(echo "$USER_DATA" | python3 -c "import sys,json; print(json.load(sys.stdin)['login'])")
echo "✅ Token VALID — Authenticated as: $USERNAME"

# 2. Check token type (classic vs fine-grained)
echo ""
echo "--- Step 2: Token Type ---"
SCOPES=$(curl -sI -H "Authorization: token $TOKEN" https://api.github.com/user 2>&1 | grep -i "^x-oauth-scopes:" | sed 's/.*: //')

if [ -z "$SCOPES" ]; then
  echo "🔹 Fine-Grained PAT (github_pat_...)"
  echo "   No traditional OAuth scopes — uses repository/account-level permissions."
  echo "   To check/update permissions: https://github.com/settings/tokens"
else
  echo "🔹 Classic PAT"
  echo "   Scopes: $SCOPES"
fi

# 3. Test repo creation permission
echo ""
echo "--- Step 3: Repo Creation Permission ---"
TEST_RESP=$(curl -s -w "\n%{http_code}" -X POST \
  -H "Authorization: token $TOKEN" \
  https://api.github.com/user/repos \
  -d '{"name": "_hermes_diag_test", "private": true, "auto_init": false}')
TEST_CODE=$(echo "$TEST_RESP" | tail -1)
TEST_DATA=$(echo "$TEST_RESP" | sed '$d')

if [ "$TEST_CODE" = "201" ]; then
  echo "✅ Repo creation: ALLOWED"
  # Clean up test repo
  curl -s -X DELETE -H "Authorization: token $TOKEN" "https://api.github.com/repos/${USERNAME}/_hermes_diag_test" > /dev/null
elif [ "$TEST_CODE" = "403" ]; then
  ERROR_MSG=$(echo "$TEST_DATA" | python3 -c "import sys,json; print(json.load(sys.stdin).get('message','unknown'))" 2>/dev/null)
  echo "❌ Repo creation: DENIED"
  echo "   Error: $ERROR_MSG"
  echo ""
  if [ -z "$SCOPES" ]; then
    echo "   Fine-Grained PAT fix → Set Account permissions: Repository creation → Write"
    echo "   Or generate a Classic PAT with 'repo' scope instead."
  else
    echo "   Classic PAT fix → Missing 'public_repo' or 'repo' scope."
  fi
elif [ "$TEST_CODE" = "422" ]; then
  echo "⚠️  Repo creation: ambiguous (422 — may already exist from prior run)"
  echo "   Assuming token works if you're reading this after a clean run."
fi

echo ""
echo "=== Diagnosis Complete ==="
