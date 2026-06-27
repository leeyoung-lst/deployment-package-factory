#!/usr/bin/env bash
set -euo pipefail

REGISTRY=""
REPOSITORY="platform"
TAG="latest"
OUTPUT_DIR="deploy/generated"
HTTP_PORT="5186"

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
    --output-dir)
      OUTPUT_DIR="$2"
      shift 2
      ;;
    --http-port)
      HTTP_PORT="$2"
      shift 2
      ;;
    *)
      echo "Usage: scripts/render-deploy-images.sh --registry REGISTRY [--repository REPOSITORY] [--tag TAG] [--output-dir DIR] [--http-port PORT]" >&2
      exit 1
      ;;
  esac
done

if [ -z "${REGISTRY}" ]; then
  echo "--registry is required, for example: --registry registry.example.com" >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
if [[ "${OUTPUT_DIR}" = /* ]]; then
  TARGET_DIR="${OUTPUT_DIR}"
else
  TARGET_DIR="${REPO_ROOT}/${OUTPUT_DIR}"
fi
mkdir -p "${TARGET_DIR}"

PREFIX="${REGISTRY%/}"
REPOSITORY="${REPOSITORY#/}"
REPOSITORY="${REPOSITORY%/}"
if [ -n "${REPOSITORY}" ]; then
  PREFIX="${PREFIX}/${REPOSITORY}"
fi

BACKEND_IMAGE="${PREFIX}/deployment-package-factory-backend:${TAG}"
FRONTEND_IMAGE="${PREFIX}/deployment-package-factory-frontend:${TAG}"

cat > "${TARGET_DIR}/factory.env" <<EOF
DPF_BACKEND_IMAGE=${BACKEND_IMAGE}
DPF_FRONTEND_IMAGE=${FRONTEND_IMAGE}
DPF_HTTP_PORT=${HTTP_PORT}
EOF

cat > "${TARGET_DIR}/kustomization.yaml" <<EOF
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - ../k8s
images:
  - name: deployment-package-factory-backend
    newName: ${PREFIX}/deployment-package-factory-backend
    newTag: ${TAG}
  - name: deployment-package-factory-frontend
    newName: ${PREFIX}/deployment-package-factory-frontend
    newTag: ${TAG}
EOF

echo "Generated deployment image files:"
echo "  ${TARGET_DIR}/factory.env"
echo "  ${TARGET_DIR}/kustomization.yaml"
