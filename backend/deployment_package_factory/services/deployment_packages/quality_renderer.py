from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath


QUALITY_GATE_VERSION = "1.0.0"
QUALITY_GATE_CHECKS = ["verify", "mcp-connectivity", "k8s-dry-run", "docker-compose-config"]


@dataclass(frozen=True)
class RenderedQualityFile:
    path: PurePosixPath
    content: str
    executable: bool = False


def render_quality_gate_files(manifest: dict) -> list[RenderedQualityFile]:
    return [
        RenderedQualityFile(PurePosixPath("quality-gate.sh"), _quality_gate_sh(manifest), executable=True),
        RenderedQualityFile(PurePosixPath("quality-gate.ps1"), _quality_gate_ps1()),
        RenderedQualityFile(PurePosixPath("docs/quality-report.md"), _quality_report(manifest)),
    ]


def _quality_gate_sh(manifest: dict) -> str:
    deploy_modes = " ".join(manifest.get("deployModes") or [])
    return (
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        f'QUALITY_GATE_VERSION="{QUALITY_GATE_VERSION}"\n'
        f'DEPLOY_MODES="{deploy_modes}"\n'
        'SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"\n'
        'REPORT_FILE="${SCRIPT_DIR}/docs/quality-report.runtime.md"\n'
        "\n"
        'MODE="${1:-all}"\n'
        "\n"
        "run_check() {\n"
        '  local name="$1"\n'
        "  shift\n"
        '  echo "Running quality check: ${name}"\n'
        '  if "$@"; then\n'
        '    echo "- ${name}: passed" >> "${REPORT_FILE}"\n'
        "  else\n"
        '    echo "- ${name}: failed" >> "${REPORT_FILE}"\n'
        '    echo "Quality check failed: ${name}" >&2\n'
        "    exit 1\n"
        "  fi\n"
        "}\n"
        "\n"
        "has_mode() {\n"
        '  case " ${DEPLOY_MODES} " in\n'
        '    *" $1 "*) return 0 ;;\n'
        "    *) return 1 ;;\n"
        "  esac\n"
        "}\n"
        "\n"
        'cat > "${REPORT_FILE}" <<EOF\n'
        "# Deployment Package Quality Report\n"
        "\n"
        f"- Quality gate version: {QUALITY_GATE_VERSION}\n"
        f"- Package ID: {manifest['packageId']}\n"
        f"- Project: {manifest.get('projectKey') or 'custom'}\n"
        f"- Product version: {manifest.get('productVersion') or ''}\n"
        f"- Deploy modes: {', '.join(manifest.get('deployModes') or []) or '-'}\n"
        f"- Database: {manifest.get('database') or ''}\n"
        "\n"
        "## Results\n"
        "EOF\n"
        "\n"
        'run_check "package-integrity" "${SCRIPT_DIR}/verify.sh"\n'
        'if [ "${MODE}" = "all" ] || [ "${MODE}" = "k8s" ]; then\n'
        '  if has_mode "k8s"; then\n'
        '    run_check "k8s-client-dry-run" "${SCRIPT_DIR}/k8s/dry-run.sh"\n'
        "  else\n"
        '    echo "- k8s-client-dry-run: skipped (mode not selected)" >> "${REPORT_FILE}"\n'
        "  fi\n"
        "fi\n"
        "\n"
        'if [ "${MODE}" = "all" ] || [ "${MODE}" = "docker-compose" ]; then\n'
        '  if has_mode "docker-compose"; then\n'
        '    run_check "docker-compose-config" "${SCRIPT_DIR}/docker-compose/dry-run.sh"\n'
        "  else\n"
        '    echo "- docker-compose-config: skipped (mode not selected)" >> "${REPORT_FILE}"\n'
        "  fi\n"
        "fi\n"
        "\n"
        'if [ "${MODE}" != "all" ] && [ "${MODE}" != "k8s" ] && [ "${MODE}" != "docker-compose" ]; then\n'
        '  echo "Usage: ./quality-gate.sh [all|k8s|docker-compose]" >&2\n'
        "  exit 1\n"
        "fi\n"
        "\n"
        'echo "Quality gate passed. Report: ${REPORT_FILE}"\n'
    )


def _quality_gate_ps1() -> str:
    return (
        "param(\n"
        "  [ValidateSet('all', 'k8s', 'docker-compose')]\n"
        "  [string]$Mode = 'all'\n"
        ")\n"
        "$ErrorActionPreference = 'Stop'\n"
        "$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path\n"
        "$ReportFile = Join-Path $ScriptDir 'docs/quality-report.runtime.md'\n"
        "$Manifest = [System.IO.File]::ReadAllText((Join-Path $ScriptDir 'manifest.json'), [System.Text.Encoding]::UTF8) | ConvertFrom-Json\n"
        "\n"
        "Set-Content -LiteralPath $ReportFile -Value @(\n"
        "  '# Deployment Package Quality Report',\n"
        "  '',\n"
        f"  '- Quality gate version: {QUALITY_GATE_VERSION}',\n"
        "  '',\n"
        "  '## Results'\n"
        ") -Encoding UTF8\n"
        "\n"
        "function Add-Result([string]$Name, [string]$Status) {\n"
        "  Add-Content -LiteralPath $ReportFile -Value \"- ${Name}: ${Status}\" -Encoding UTF8\n"
        "}\n"
        "\n"
        "function Run-Check([string]$Name, [scriptblock]$Command) {\n"
        "  Write-Host \"Running quality check: $Name\"\n"
        "  try {\n"
        "    & $Command\n"
        "    Add-Result $Name 'passed'\n"
        "  } catch {\n"
        "    Add-Result $Name 'failed'\n"
        "    throw\n"
        "  }\n"
        "}\n"
        "\n"
        "function Has-DeployMode([string]$DeployMode) {\n"
        "  return @($Manifest.deployModes) -contains $DeployMode\n"
        "}\n"
        "\n"
        "Run-Check 'package-integrity' { & (Join-Path $ScriptDir 'verify.ps1') }\n"
        "if ($Mode -eq 'all' -or $Mode -eq 'k8s') {\n"
        "  if (Has-DeployMode 'k8s') { Run-Check 'k8s-client-dry-run' { bash (Join-Path $ScriptDir 'k8s/dry-run.sh') } }\n"
        "  else { Add-Result 'k8s-client-dry-run' 'skipped (mode not selected)' }\n"
        "}\n"
        "if ($Mode -eq 'all' -or $Mode -eq 'docker-compose') {\n"
        "  if (Has-DeployMode 'docker-compose') { Run-Check 'docker-compose-config' { bash (Join-Path $ScriptDir 'docker-compose/dry-run.sh') } }\n"
        "  else { Add-Result 'docker-compose-config' 'skipped (mode not selected)' }\n"
        "}\n"
        "Write-Host \"Quality gate passed. Report: $ReportFile\"\n"
    )


def _quality_report(manifest: dict) -> str:
    return (
        "# Deployment Package Quality Report\n"
        "\n"
        f"- Quality gate version: {QUALITY_GATE_VERSION}\n"
        f"- Package ID: {manifest['packageId']}\n"
        f"- Project: {manifest.get('projectKey') or 'custom'}\n"
        f"- Product version: {manifest.get('productVersion') or ''}\n"
        f"- Deploy modes: {', '.join(manifest.get('deployModes') or []) or '-'}\n"
        f"- Database: {manifest.get('database') or ''}\n"
        "\n"
        "## Required Checks\n"
        "\n"
        "- package-integrity: `./verify.sh` or `./verify.ps1`\n"
        "- mcp-connectivity: `./scripts/verify-mcp.sh` or `./scripts/verify-mcp.ps1` when MCP services are included\n"
        "- k8s-client-dry-run: `./k8s/dry-run.sh`\n"
        "- docker-compose-config: `./docker-compose/dry-run.sh`\n"
        f"- MCP-enabled registered microservices: {len(_mcp_services(manifest))}\n"
        "\n"
        "## Results\n"
        "\n"
        "Run `./quality-gate.sh` from the package root to write check results to `docs/quality-report.runtime.md`.\n"
    )


def _mcp_services(manifest: dict) -> list[dict]:
    return [item for item in manifest.get("registeredMicroservices") or [] if item.get("mcpServerEnabled")]
