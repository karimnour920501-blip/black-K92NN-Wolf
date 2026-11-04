#!/usr/bin/env bash
set -euo pipefail
BASE="${BASE:-http://127.0.0.1:8080}"
: "${BLACKWOLF_ADMIN_TOKEN:?required}"
curl --fail --silent --show-error "$BASE/health"
curl --fail --silent --show-error "$BASE/ready"
code=$(curl --silent --show-error --output /dev/null --write-out '%{http_code}' "$BASE/api/projects")
test "$code" = 401
curl --fail --silent --show-error -H "X-Admin-Token: $BLACKWOLF_ADMIN_TOKEN" "$BASE/api/projects"
echo SMOKE_PASS
