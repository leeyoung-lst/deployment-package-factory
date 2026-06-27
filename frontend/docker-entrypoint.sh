#!/bin/sh
set -eu

CONFIG_FILE="/usr/share/nginx/html/runtime-config.js"

json_string() {
  printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g; s/\r//g; s/$/\\n/' | tr -d '\n' | sed 's/\\n$//'
}

API_BASE_URL="$(json_string "${DEPLOYMENT_PACKAGE_FRONTEND_API_BASE_URL:-}")"
API_TOKEN="$(json_string "${DEPLOYMENT_PACKAGE_FRONTEND_API_TOKEN:-}")"

cat > "${CONFIG_FILE}" <<EOF
window.__DEPLOYMENT_PACKAGE_FACTORY_CONFIG__ = {
  apiBaseUrl: "${API_BASE_URL}",
  apiToken: "${API_TOKEN}",
};
EOF

exec nginx -g "daemon off;"
