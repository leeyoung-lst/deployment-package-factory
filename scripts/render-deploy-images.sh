#!/usr/bin/env bash
set -euo pipefail

REGISTRY=""
REPOSITORY="platform"
TAG="latest"
OUTPUT_DIR="deploy/generated"
HTTP_PORT="5186"
DATABASE_URL=""
STORAGE_CLASS=""

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
    --database-url)
      DATABASE_URL="$2"
      shift 2
      ;;
    --storage-class)
      STORAGE_CLASS="$2"
      shift 2
      ;;
    *)
      echo "Usage: scripts/render-deploy-images.sh --registry REGISTRY --storage-class STORAGE_CLASS [--repository REPOSITORY] [--tag TAG] [--output-dir DIR] [--http-port PORT] [--database-url URL]" >&2
      exit 1
      ;;
  esac
done

if [ -z "${REGISTRY}" ]; then
  echo "--registry is required, for example: --registry registry.example.com" >&2
  exit 1
fi
if [ -z "${STORAGE_CLASS}" ]; then
  echo "--storage-class is required for Kubernetes deployment config, for example: --storage-class nfs-rwx" >&2
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
WORKER_IMAGE="${PREFIX}/deployment-package-factory-worker:${TAG}"
FRONTEND_IMAGE="${PREFIX}/deployment-package-factory-frontend:${TAG}"

cat > "${TARGET_DIR}/factory.env" <<EOF
DPF_BACKEND_IMAGE=${BACKEND_IMAGE}
DPF_WORKER_IMAGE=${WORKER_IMAGE}
DPF_FRONTEND_IMAGE=${FRONTEND_IMAGE}
DPF_HTTP_PORT=${HTTP_PORT}
DEPLOYMENT_PACKAGE_DATABASE_URL=${DATABASE_URL}
EOF

cat > "${TARGET_DIR}/kustomization.yaml" <<EOF
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - ../k8s
patches:
  - path: pvc-storage-class-patch.yaml
images:
  - name: deployment-package-factory-backend
    newName: ${PREFIX}/deployment-package-factory-backend
    newTag: ${TAG}
  - name: deployment-package-factory-worker
    newName: ${PREFIX}/deployment-package-factory-worker
    newTag: ${TAG}
  - name: deployment-package-factory-frontend
    newName: ${PREFIX}/deployment-package-factory-frontend
    newTag: ${TAG}
EOF

cat > "${TARGET_DIR}/pvc-storage-class-patch.yaml" <<EOF
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: deployment-package-factory-data
  namespace: deployment-package-factory
spec:
  storageClassName: ${STORAGE_CLASS}
EOF

echo "Generated deployment image files:"
echo "  ${TARGET_DIR}/factory.env"
echo "  ${TARGET_DIR}/kustomization.yaml"
echo "  ${TARGET_DIR}/pvc-storage-class-patch.yaml"
