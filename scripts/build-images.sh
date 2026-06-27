#!/usr/bin/env bash
set -euo pipefail

REGISTRY=""
REPOSITORY="platform"
TAG="latest"
NO_CACHE=0

while [ "$#" -gt 0 ]; do
  case "$1" in
    --registry)
      REGISTRY="$2"
      shift 2
      ;;
    --repository)
      REPOSITORY="$2"
      shift 2
      ;;
    --tag)
      TAG="$2"
      shift 2
      ;;
    --no-cache)
      NO_CACHE=1
      shift
      ;;
    *)
      echo "Usage: scripts/build-images.sh [--registry REGISTRY] [--repository REPOSITORY] [--tag TAG] [--no-cache]" >&2
      exit 1
      ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
PREFIX=""
if [ -n "${REGISTRY}" ]; then
  PREFIX="${REGISTRY%/}"
  REPOSITORY="${REPOSITORY#/}"
  REPOSITORY="${REPOSITORY%/}"
  if [ -n "${REPOSITORY}" ]; then
    PREFIX="${PREFIX}/${REPOSITORY}"
  fi
fi

image_name() {
  if [ -n "${PREFIX}" ]; then
    printf "%s/%s:%s" "${PREFIX}" "$1" "${TAG}"
  else
    printf "%s:%s" "$1" "${TAG}"
  fi
}

BACKEND_IMAGE="$(image_name deployment-package-factory-backend)"
FRONTEND_IMAGE="$(image_name deployment-package-factory-frontend)"
BUILD_ARGS=()
if [ "${NO_CACHE}" = "1" ]; then
  BUILD_ARGS+=(--no-cache)
fi

echo "Building ${BACKEND_IMAGE}"
docker build "${BUILD_ARGS[@]}" -f "${REPO_ROOT}/backend/Dockerfile" -t "${BACKEND_IMAGE}" "${REPO_ROOT}"

echo "Building ${FRONTEND_IMAGE}"
docker build "${BUILD_ARGS[@]}" -f "${REPO_ROOT}/frontend/Dockerfile" -t "${FRONTEND_IMAGE}" "${REPO_ROOT}"

echo "Built images:"
echo "  ${BACKEND_IMAGE}"
echo "  ${FRONTEND_IMAGE}"
