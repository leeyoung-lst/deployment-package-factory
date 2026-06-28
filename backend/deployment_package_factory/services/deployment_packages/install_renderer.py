from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath


INSTALLER_VERSION = "1.2.0"
INSTALLER_OPTIONS = ["--skip-verify", "--skip-dry-run", "--skip-health-check", "--yes"]


@dataclass(frozen=True)
class RenderedInstallFile:
    path: PurePosixPath
    content: str
    executable: bool = False


def render_root_install_files(manifest: dict | None = None) -> list[RenderedInstallFile]:
    default_mode = _default_deploy_mode(manifest)
    return [
        RenderedInstallFile(PurePosixPath("install.sh"), _install_sh(), executable=True),
        RenderedInstallFile(PurePosixPath("install.ps1"), _install_ps1(default_mode)),
    ]


def _default_deploy_mode(manifest: dict | None) -> str:
    deploy_modes = list((manifest or {}).get("deployModes") or [])
    if "k8s" not in deploy_modes and "docker-compose" in deploy_modes:
        return "docker-compose"
    return "k8s"


def _install_sh() -> str:
    return (
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        f'INSTALLER_VERSION="{INSTALLER_VERSION}"\n'
        'MODE="${1:-k8s}"\n'
        "SKIP_DRY_RUN=0\n"
        "SKIP_HEALTH_CHECK=0\n"
        "SKIP_VERIFY=0\n"
        "ASSUME_YES=0\n"
        'SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"\n'
        'INDEX_FILE="${SCRIPT_DIR}/package-index.json"\n'
        "\n"
        "shift || true\n"
        'while [ "$#" -gt 0 ]; do\n'
        '  case "$1" in\n'
        "    --skip-verify)\n"
        "      SKIP_VERIFY=1\n"
        "      ;;\n"
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
        '      echo "Usage: ./install.sh [k8s|docker-compose] [--skip-verify] [--skip-dry-run] [--skip-health-check] [--yes]" >&2\n'
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
        'if [ "${SKIP_VERIFY}" != "1" ]; then\n'
        '  "${SCRIPT_DIR}/verify.sh"\n'
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
        '    echo "Usage: ./install.sh [k8s|docker-compose] [--skip-verify] [--skip-dry-run] [--skip-health-check] [--yes]" >&2\n'
        "    exit 1\n"
        "    ;;\n"
        "esac\n"
    )


def _install_ps1(default_mode: str = "k8s") -> str:
    return (
        "param(\n"
        "  [ValidateSet('k8s', 'docker-compose')]\n"
        f"  [string]$Mode = '{default_mode}',\n"
        "  [switch]$SkipVerify,\n"
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
        "$Manifest = Get-Content -LiteralPath (Join-Path $ScriptDir 'manifest.json') -Raw | ConvertFrom-Json\n"
        "if (@($Manifest.deployModes) -notcontains $Mode) {\n"
        "  throw \"Deploy mode '$Mode' is not included in this package. Available modes: $(@($Manifest.deployModes) -join ', ')\"\n"
        "}\n"
        "\n"
        "function Require-Command([string]$Name) {\n"
        "  if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {\n"
        "    throw \"Missing required command: $Name\"\n"
        "  }\n"
        "}\n"
        "\n"
        "function Test-PackageDiskSpace {\n"
        "  $requiredBytes = 0\n"
        "  if ($Manifest.validationSummary -and $Manifest.validationSummary.packageIndexTotalBytes) {\n"
        "    $requiredBytes = [int64]$Manifest.validationSummary.packageIndexTotalBytes\n"
        "  }\n"
        "  if ($requiredBytes -le 0) {\n"
        "    Write-Host 'Disk space check skipped: package size metadata unavailable.'\n"
        "    return\n"
        "  }\n"
        "  $root = Get-Item -LiteralPath $ScriptDir\n"
        "  $drive = Get-PSDrive -Name $root.PSDrive.Name\n"
        "  $minimumBytes = $requiredBytes * 2\n"
        "  if ($drive.Free -lt $minimumBytes) {\n"
        "    throw \"Insufficient disk space: need at least $minimumBytes bytes, available $($drive.Free) bytes.\"\n"
        "  }\n"
        "  Write-Host \"Disk space check passed: available $($drive.Free) bytes.\"\n"
        "}\n"
        "\n"
        "function Test-ImageArchives {\n"
        "  $valuesPath = Join-Path $ScriptDir 'deploy-values.json'\n"
        "  if (-not (Test-Path -LiteralPath $valuesPath -PathType Leaf)) {\n"
        "    Write-Host 'deploy-values.json not found; image archive preflight skipped.'\n"
        "    return\n"
        "  }\n"
        "  $values = Get-Content -LiteralPath $valuesPath -Raw | ConvertFrom-Json\n"
        "  if ($values.imageMode -ne 'image-archive') { return }\n"
        "  $missing = @()\n"
        "  foreach ($image in @($values.images)) {\n"
        "    if ($image.archiveFile) {\n"
        "      $archivePath = Join-Path (Join-Path $ScriptDir 'images/archives') $image.archiveFile\n"
        "      if (-not (Test-Path -LiteralPath $archivePath -PathType Leaf)) { $missing += $image.archiveFile }\n"
        "    }\n"
        "  }\n"
        "  if ($missing.Count) { throw \"Missing image archives: $($missing -join ', ')\" }\n"
        "  Write-Host 'Image archive preflight passed.'\n"
        "}\n"
        "\n"
        "function Get-ComposeEnvFile([switch]$RequireConcreteEnv) {\n"
        "  $composeDir = Join-Path $ScriptDir 'docker-compose'\n"
        "  $envFile = Join-Path $composeDir '.env'\n"
        "  if (Test-Path -LiteralPath $envFile -PathType Leaf) { return $envFile }\n"
        "  $templateFile = Join-Path $composeDir '.env.template'\n"
        "  if ($RequireConcreteEnv) {\n"
        "    throw 'docker-compose/.env not found. Copy docker-compose/.env.template to docker-compose/.env and replace all __REPLACE_WITH_ values before installation.'\n"
        "  }\n"
        "  return $templateFile\n"
        "}\n"
        "\n"
        "function Test-SecretPlaceholders([string]$EnvFile) {\n"
        "  if (-not (Test-Path -LiteralPath $EnvFile -PathType Leaf)) {\n"
        "    throw \"Secret file not found: $EnvFile\"\n"
        "  }\n"
        "  $matches = Select-String -LiteralPath $EnvFile -Pattern '__REPLACE_WITH_' -SimpleMatch\n"
        "  if ($matches) {\n"
        "    $details = @($matches | ForEach-Object { \"$($_.Path):$($_.LineNumber):$($_.Line.Trim())\" }) -join [Environment]::NewLine\n"
        "    throw (\"Secret placeholders remain. Replace them before installation:\" + [Environment]::NewLine + $details)\n"
        "  }\n"
        "  Write-Host 'Secret placeholder check passed.'\n"
        "}\n"
        "\n"
        "function Test-DockerComposePrerequisites {\n"
        "  Require-Command 'docker'\n"
        "  & docker info | Out-Null\n"
        "  & docker compose version | Out-Null\n"
        "  Test-PackageDiskSpace\n"
        "  Test-ImageArchives\n"
        "  Write-Host 'Prerequisite check passed for docker-compose.'\n"
        "}\n"
        "\n"
        "function Invoke-DockerComposeDryRun {\n"
        "  Test-DockerComposePrerequisites\n"
        "  $envFile = Get-ComposeEnvFile -RequireConcreteEnv\n"
        "  Test-SecretPlaceholders $envFile\n"
        "  & docker compose --env-file $envFile -f (Join-Path $ScriptDir 'docker-compose/docker-compose.yml') config\n"
        "}\n"
        "\n"
        "function Invoke-DockerComposeInstall {\n"
        "  Test-DockerComposePrerequisites\n"
        "  $envFile = Get-ComposeEnvFile -RequireConcreteEnv\n"
        "  Test-SecretPlaceholders $envFile\n"
        "  & docker compose --env-file $envFile -f (Join-Path $ScriptDir 'docker-compose/docker-compose.yml') up -d\n"
        "  $initScript = Join-Path $ScriptDir 'init/run-init.ps1'\n"
        "  if (Test-Path -LiteralPath $initScript -PathType Leaf) { & $initScript all }\n"
        "  else { Write-Host 'Init scripts are available under init/. Run them after services are configured.' }\n"
        "}\n"
        "\n"
        "function Invoke-DockerComposeHealthCheck {\n"
        "  Require-Command 'docker'\n"
        "  $envFile = Get-ComposeEnvFile -RequireConcreteEnv\n"
        "  & docker compose --env-file $envFile -f (Join-Path $ScriptDir 'docker-compose/docker-compose.yml') ps\n"
        "}\n"
        "\n"
        "if (-not $SkipVerify) {\n"
        "  & (Join-Path $ScriptDir 'verify.ps1')\n"
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
        "  if (-not $SkipDryRun) { Invoke-DockerComposeDryRun }\n"
        "  Invoke-DockerComposeInstall\n"
        "  if (-not $SkipHealthCheck) { Invoke-DockerComposeHealthCheck }\n"
        "}\n"
    )
