from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath

from deployment_package_factory.services.deployment_packages.root_install_powershell import render_install_ps1
from deployment_package_factory.services.deployment_packages.root_install_shell import render_install_sh


INSTALLER_VERSION = "1.2.0"
INSTALLER_OPTIONS = ["--skip-verify", "--skip-dry-run", "--skip-health-check", "--skip-diagnostics", "--yes"]


@dataclass(frozen=True)
class RenderedInstallFile:
    path: PurePosixPath
    content: str
    executable: bool = False


def render_root_install_files(manifest: dict | None = None) -> list[RenderedInstallFile]:
    default_mode = _default_deploy_mode(manifest)
    return [
        RenderedInstallFile(PurePosixPath("install.sh"), render_install_sh(INSTALLER_VERSION), executable=True),
        RenderedInstallFile(PurePosixPath("install.ps1"), render_install_ps1(INSTALLER_VERSION, default_mode)),
    ]


def _default_deploy_mode(manifest: dict | None) -> str:
    deploy_modes = list((manifest or {}).get("deployModes") or [])
    if "k8s" not in deploy_modes and "docker-compose" in deploy_modes:
        return "docker-compose"
    return "k8s"
