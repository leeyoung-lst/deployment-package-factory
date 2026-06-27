from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath


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
        'MODE="${1:-k8s}"\n'
        'SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"\n'
        'INDEX_FILE="${SCRIPT_DIR}/package-index.json"\n'
        "\n"
        'if [ ! -f "${INDEX_FILE}" ]; then\n'
        '  echo "package-index.json not found. Run this script from the deployment package root." >&2\n'
        "  exit 1\n"
        "fi\n"
        "\n"
        'case "${MODE}" in\n'
        "  k8s)\n"
        '    "${SCRIPT_DIR}/k8s/dry-run.sh"\n'
        '    "${SCRIPT_DIR}/k8s/install.sh"\n'
        '    "${SCRIPT_DIR}/scripts/health-check.sh" k8s\n'
        "    ;;\n"
        "  docker-compose)\n"
        '    "${SCRIPT_DIR}/docker-compose/dry-run.sh"\n'
        '    "${SCRIPT_DIR}/docker-compose/install.sh"\n'
        '    "${SCRIPT_DIR}/scripts/health-check.sh" docker-compose\n'
        "    ;;\n"
        "  *)\n"
        '    echo "Usage: ./install.sh [k8s|docker-compose]" >&2\n'
        "    exit 1\n"
        "    ;;\n"
        "esac\n"
    )


def _install_ps1() -> str:
    return (
        "param(\n"
        "  [ValidateSet('k8s', 'docker-compose')]\n"
        "  [string]$Mode = 'k8s'\n"
        ")\n"
        "$ErrorActionPreference = 'Stop'\n"
        "$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path\n"
        "$IndexFile = Join-Path $ScriptDir 'package-index.json'\n"
        "\n"
        "if (-not (Test-Path -LiteralPath $IndexFile)) {\n"
        "  throw 'package-index.json not found. Run this script from the deployment package root.'\n"
        "}\n"
        "\n"
        "if ($Mode -eq 'k8s') {\n"
        "  bash (Join-Path $ScriptDir 'k8s/dry-run.sh')\n"
        "  bash (Join-Path $ScriptDir 'k8s/install.sh')\n"
        "  bash (Join-Path $ScriptDir 'scripts/health-check.sh') k8s\n"
        "} else {\n"
        "  bash (Join-Path $ScriptDir 'docker-compose/dry-run.sh')\n"
        "  bash (Join-Path $ScriptDir 'docker-compose/install.sh')\n"
        "  bash (Join-Path $ScriptDir 'scripts/health-check.sh') docker-compose\n"
        "}\n"
    )
