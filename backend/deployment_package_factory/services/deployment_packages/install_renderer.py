from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath


INSTALLER_VERSION = "1.1.0"
INSTALLER_OPTIONS = ["--skip-dry-run", "--skip-health-check", "--yes"]


@dataclass(frozen=True)
class RenderedInstallFile:
    path: PurePosixPath
    content: str
    executable: bool = False


def render_root_install_files() -> list[RenderedInstallFile]:
    return [
        RenderedInstallFile(PurePosixPath("install.sh"), _install_sh(), executable=True),
        RenderedInstallFile(PurePosixPath("install.ps1"), _install_ps1()),
    ]


def _install_sh() -> str:
    return (
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        f'INSTALLER_VERSION="{INSTALLER_VERSION}"\n'
        'MODE="${1:-k8s}"\n'
        "SKIP_DRY_RUN=0\n"
        "SKIP_HEALTH_CHECK=0\n"
        "ASSUME_YES=0\n"
        'SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"\n'
        'INDEX_FILE="${SCRIPT_DIR}/package-index.json"\n'
        "\n"
        "shift || true\n"
        'while [ "$#" -gt 0 ]; do\n'
        '  case "$1" in\n'
        "    --skip-dry-run)\n"
        "      SKIP_DRY_RUN=1\n"
        "      ;;\n"
        "    --skip-health-check)\n"
        "      SKIP_HEALTH_CHECK=1\n"
        "      ;;\n"
        "    --yes|-y)\n"
        "      ASSUME_YES=1\n"
        "      ;;\n"
        "    *)\n"
        '      echo "Unknown option: $1" >&2\n'
        '      echo "Usage: ./install.sh [k8s|docker-compose] [--skip-dry-run] [--skip-health-check] [--yes]" >&2\n'
        "      exit 1\n"
        "      ;;\n"
        "  esac\n"
        "  shift\n"
        "done\n"
        "\n"
        'if [ ! -f "${INDEX_FILE}" ]; then\n'
        '  echo "package-index.json not found. Run this script from the deployment package root." >&2\n'
        "  exit 1\n"
        "fi\n"
        "\n"
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
        '    "${SCRIPT_DIR}/k8s/dry-run.sh"\n'
        "    fi\n"
        '    "${SCRIPT_DIR}/k8s/install.sh"\n'
        '    if [ "${SKIP_HEALTH_CHECK}" != "1" ]; then\n'
        '    "${SCRIPT_DIR}/scripts/health-check.sh" k8s\n'
        "    fi\n"
        "    ;;\n"
        "  docker-compose)\n"
        '    if [ "${SKIP_DRY_RUN}" != "1" ]; then\n'
        '    "${SCRIPT_DIR}/docker-compose/dry-run.sh"\n'
        "    fi\n"
        '    "${SCRIPT_DIR}/docker-compose/install.sh"\n'
        '    if [ "${SKIP_HEALTH_CHECK}" != "1" ]; then\n'
        '    "${SCRIPT_DIR}/scripts/health-check.sh" docker-compose\n'
        "    fi\n"
        "    ;;\n"
        "  *)\n"
        '    echo "Usage: ./install.sh [k8s|docker-compose] [--skip-dry-run] [--skip-health-check] [--yes]" >&2\n'
        "    exit 1\n"
        "    ;;\n"
        "esac\n"
    )


def _install_ps1() -> str:
    return (
        "param(\n"
        "  [ValidateSet('k8s', 'docker-compose')]\n"
        "  [string]$Mode = 'k8s',\n"
        "  [switch]$SkipDryRun,\n"
        "  [switch]$SkipHealthCheck,\n"
        "  [switch]$Yes\n"
        ")\n"
        "$ErrorActionPreference = 'Stop'\n"
        f"$InstallerVersion = '{INSTALLER_VERSION}'\n"
        "$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path\n"
        "$IndexFile = Join-Path $ScriptDir 'package-index.json'\n"
        "\n"
        "if (-not (Test-Path -LiteralPath $IndexFile)) {\n"
        "  throw 'package-index.json not found. Run this script from the deployment package root.'\n"
        "}\n"
        "\n"
        "if (-not $Yes) {\n"
        "  Write-Host \"Installer $InstallerVersion will deploy mode: $Mode\"\n"
        "  $answer = Read-Host 'Continue? [y/N]'\n"
        "  if ($answer -ne 'y' -and $answer -ne 'Y') {\n"
        "    Write-Host 'Installation canceled.'\n"
        "    exit 0\n"
        "  }\n"
        "}\n"
        "\n"
        "if ($Mode -eq 'k8s') {\n"
        "  if (-not $SkipDryRun) { bash (Join-Path $ScriptDir 'k8s/dry-run.sh') }\n"
        "  bash (Join-Path $ScriptDir 'k8s/install.sh')\n"
        "  if (-not $SkipHealthCheck) { bash (Join-Path $ScriptDir 'scripts/health-check.sh') k8s }\n"
        "} else {\n"
        "  if (-not $SkipDryRun) { bash (Join-Path $ScriptDir 'docker-compose/dry-run.sh') }\n"
        "  bash (Join-Path $ScriptDir 'docker-compose/install.sh')\n"
        "  if (-not $SkipHealthCheck) { bash (Join-Path $ScriptDir 'scripts/health-check.sh') docker-compose }\n"
        "}\n"
    )
