from __future__ import annotations


def render_install_sh(installer_version: str) -> str:
    return (
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        f'INSTALLER_VERSION="{installer_version}"\n'
        'MODE="k8s"\n'
        'if [ "$#" -gt 0 ] && [ "${1#--}" = "$1" ]; then\n'
        '  MODE="$1"\n'
        "  shift\n"
        "fi\n"
        "SKIP_DIAGNOSTICS=0\n"
        "SKIP_DRY_RUN=0\n"
        "SKIP_HEALTH_CHECK=0\n"
        "SKIP_VERIFY=0\n"
        "ASSUME_YES=0\n"
        'SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"\n'
        'INDEX_FILE="${SCRIPT_DIR}/package-index.json"\n'
        "\n"
        "usage() {\n"
        '  echo "Usage: ./install.sh [k8s|docker-compose] [--skip-verify] [--skip-dry-run] [--skip-health-check] [--skip-diagnostics] [--yes]" >&2\n'
        "}\n"
        "\n"
        'while [ "$#" -gt 0 ]; do\n'
        '  case "$1" in\n'
        "    --skip-verify) SKIP_VERIFY=1 ;;\n"
        "    --skip-dry-run) SKIP_DRY_RUN=1 ;;\n"
        "    --skip-health-check) SKIP_HEALTH_CHECK=1 ;;\n"
        "    --skip-diagnostics) SKIP_DIAGNOSTICS=1 ;;\n"
        "    --yes|-y) ASSUME_YES=1 ;;\n"
        '    *) echo "Unknown option: $1" >&2; usage; exit 1 ;;\n'
        "  esac\n"
        "  shift\n"
        "done\n"
        "\n"
        "run_post_deploy_checks() {\n"
        '  local mode="$1"\n'
        '  if [ "${SKIP_HEALTH_CHECK}" != "1" ]; then\n'
        '    "${SCRIPT_DIR}/scripts/health-check.sh" "${mode}"\n'
        "  fi\n"
        '  if [ "${SKIP_DIAGNOSTICS}" != "1" ]; then\n'
        '    "${SCRIPT_DIR}/scripts/diagnostics.sh" "${mode}"\n'
        "  fi\n"
        '  echo "Deployment succeeded for mode: ${mode}."\n'
        "}\n"
        "\n"
        'if [ ! -f "${INDEX_FILE}" ]; then\n'
        '  echo "package-index.json not found. Run this script from the deployment package root." >&2\n'
        "  exit 1\n"
        "fi\n"
        'if [ "${SKIP_VERIFY}" != "1" ]; then\n'
        '  "${SCRIPT_DIR}/verify.sh"\n'
        "fi\n"
        'if [ "${ASSUME_YES}" != "1" ]; then\n'
        '  echo "Installer ${INSTALLER_VERSION} will deploy mode: ${MODE}"\n'
        '  read -r -p "Continue? [y/N] " answer\n'
        '  if [ "${answer}" != "y" ] && [ "${answer}" != "Y" ]; then\n'
        '    echo "Installation canceled."\n'
        "    exit 0\n"
        "  fi\n"
        "fi\n"
        "\n"
        'case "${MODE}" in\n'
        "  k8s)\n"
        '    if [ "${SKIP_DRY_RUN}" != "1" ]; then\n'
        '      "${SCRIPT_DIR}/k8s/dry-run.sh"\n'
        "    fi\n"
        '    "${SCRIPT_DIR}/k8s/install.sh"\n'
        '    run_post_deploy_checks "k8s"\n'
        "    ;;\n"
        "  docker-compose)\n"
        '    if [ "${SKIP_DRY_RUN}" != "1" ]; then\n'
        '      "${SCRIPT_DIR}/docker-compose/dry-run.sh"\n'
        "    fi\n"
        '    "${SCRIPT_DIR}/docker-compose/install.sh"\n'
        '    run_post_deploy_checks "docker-compose"\n'
        "    ;;\n"
        "  *)\n"
        "    usage\n"
        "    exit 1\n"
        "    ;;\n"
        "esac\n"
    )
