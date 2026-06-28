#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

python "${SCRIPT_DIR}/render_source_environments.py" \
  --config "${REPO_ROOT}/deploy/source-environments/source-environments.yaml" \
  --output-dir "${REPO_ROOT}/deploy/source-environments"
