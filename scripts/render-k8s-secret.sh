#!/usr/bin/env bash
set -euo pipefail

API_TOKEN=""
FRONTEND_API_TOKEN=""
DATABASE_URL=""
OUTPUT_FILE="deploy/k8s/secret.yaml"

while [ "$#" -gt 0 ]; do
  case "$1" in
    --api-token)
      API_TOKEN="$2"
      shift 2
      ;;
    --frontend-api-token)
      FRONTEND_API_TOKEN="$2"
      shift 2
      ;;
    --database-url)
      DATABASE_URL="$2"
      shift 2
      ;;
    --output-file)
      OUTPUT_FILE="$2"
      shift 2
      ;;
    *)
      echo "Usage: scripts/render-k8s-secret.sh --api-token TOKEN --frontend-api-token TOKEN --database-url URL [--output-file FILE]" >&2
      exit 1
      ;;
  esac
done

if [ -z "${API_TOKEN}" ]; then
  echo "--api-token is required" >&2
  exit 1
fi
if [ -z "${FRONTEND_API_TOKEN}" ]; then
  echo "--frontend-api-token is required" >&2
  exit 1
fi
if [ -z "${DATABASE_URL}" ]; then
  echo "--database-url is required" >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
if [[ "${OUTPUT_FILE}" = /* ]]; then
  TARGET_FILE="${OUTPUT_FILE}"
else
  TARGET_FILE="${REPO_ROOT}/${OUTPUT_FILE}"
fi
mkdir -p "$(dirname "${TARGET_FILE}")"

kubectl create secret generic deployment-package-factory-secret \
  --namespace deployment-package-factory \
  --from-literal "DEPLOYMENT_PACKAGE_API_TOKEN=${API_TOKEN}" \
  --from-literal "DEPLOYMENT_PACKAGE_FRONTEND_API_TOKEN=${FRONTEND_API_TOKEN}" \
  --from-literal "DEPLOYMENT_PACKAGE_DATABASE_URL=${DATABASE_URL}" \
  --dry-run=client \
  -o yaml > "${TARGET_FILE}"

echo "Generated ${TARGET_FILE}"
