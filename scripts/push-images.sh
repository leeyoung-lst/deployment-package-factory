#!/usr/bin/env bash
set -euo pipefail

REGISTRY=""
REPOSITORY="platform"
TAG="latest"

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
    *)
      echo "Usage: scripts/push-images.sh --registry REGISTRY [--repository REPOSITORY] [--tag TAG]" >&2
      exit 1
      ;;
  esac
done

if [ -z "${REGISTRY}" ]; then
  echo "--registry is required, for example: --registry registry.example.com" >&2
  exit 1
fi

PREFIX="${REGISTRY%/}"
REPOSITORY="${REPOSITORY#/}"
REPOSITORY="${REPOSITORY%/}"
if [ -n "${REPOSITORY}" ]; then
  PREFIX="${PREFIX}/${REPOSITORY}"
fi

IMAGES=(
  "${PREFIX}/deployment-package-factory-backend:${TAG}"
  "${PREFIX}/deployment-package-factory-worker:${TAG}"
  "${PREFIX}/deployment-package-factory-frontend:${TAG}"
)

for image in "${IMAGES[@]}"; do
  echo "Pushing ${image}"
  docker push "${image}"
done

echo "Pushed images:"
printf "  %s\n" "${IMAGES[@]}"
