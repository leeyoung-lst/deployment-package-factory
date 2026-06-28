#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-k8s}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

fail() {
  echo "Deployment config validation failed: $1" >&2
  exit 1
}

require_file() {
  if [ ! -f "${ROOT_DIR}/$1" ]; then
    fail "missing required file: $1"
  fi
}

reject_placeholders() {
  local file="$1"
  if grep -q "__REPLACE_WITH_" "${ROOT_DIR}/${file}"; then
    fail "placeholder remains in ${file}"
  fi
}

case "${MODE}" in
  k8s)
    require_file "deploy/k8s/pvc.yaml"
    require_file "deploy/k8s/secret.yaml"
    require_file "deploy/k8s/kustomization.yaml"
    reject_placeholders "deploy/k8s/pvc.yaml"
    reject_placeholders "deploy/k8s/secret.yaml"
    if ! grep -q -- "- secret.yaml" "${ROOT_DIR}/deploy/k8s/kustomization.yaml"; then
      fail "deploy/k8s/kustomization.yaml must include deploy/k8s/secret.yaml"
    fi
    if ! grep -q "ReadWriteMany" "${ROOT_DIR}/deploy/k8s/pvc.yaml"; then
      fail "deploy/k8s/pvc.yaml must use ReadWriteMany for shared artifact storage"
    fi
    if ! grep -q "DEPLOYMENT_PACKAGE_DATABASE_URL" "${ROOT_DIR}/deploy/k8s/secret.yaml"; then
      fail "deploy/k8s/secret.yaml must define DEPLOYMENT_PACKAGE_DATABASE_URL"
    fi
    ;;
  docker-compose)
    require_file "deploy/generated/factory.env"
    if ! grep -q "^DEPLOYMENT_PACKAGE_DATABASE_URL=" "${ROOT_DIR}/deploy/generated/factory.env"; then
      fail "deploy/generated/factory.env must define DEPLOYMENT_PACKAGE_DATABASE_URL for production compose"
    fi
    reject_placeholders "deploy/generated/factory.env"
    ;;
  *)
    echo "Usage: scripts/validate-deploy-config.sh [k8s|docker-compose]" >&2
    exit 1
    ;;
esac

echo "Deployment config validation passed for ${MODE}."
