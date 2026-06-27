from __future__ import annotations

from deployment_package_factory.services.deployment_packages.install_renderer import render_root_install_files


def test_render_root_install_files_exports_shell_and_powershell_entries() -> None:
    files = render_root_install_files()
    by_path = {item.path.as_posix(): item for item in files}

    assert "install.sh" in by_path
    assert "install.ps1" in by_path
    assert by_path["install.sh"].executable is True
    assert by_path["install.ps1"].executable is False
    assert "package-index.json" in by_path["install.sh"].content
    assert "k8s/install.sh" in by_path["install.sh"].content
    assert "docker-compose/install.sh" in by_path["install.sh"].content
    assert "scripts/health-check.sh" in by_path["install.sh"].content
    assert "ValidateSet('k8s', 'docker-compose')" in by_path["install.ps1"].content
