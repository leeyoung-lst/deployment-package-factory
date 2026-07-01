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
    assert 'INSTALLER_VERSION="1.2.0"' in by_path["install.sh"].content
    assert "--skip-verify" in by_path["install.sh"].content
    assert "--skip-dry-run" in by_path["install.sh"].content
    assert "--skip-health-check" in by_path["install.sh"].content
    assert "--skip-diagnostics" in by_path["install.sh"].content
    assert "--yes" in by_path["install.sh"].content
    assert "k8s/install.sh" in by_path["install.sh"].content
    assert "docker-compose/install.sh" in by_path["install.sh"].content
    assert "scripts/health-check.sh" in by_path["install.sh"].content
    assert "scripts/diagnostics.sh" in by_path["install.sh"].content
    assert "Deployment succeeded for mode:" in by_path["install.sh"].content
    assert "verify.sh" in by_path["install.sh"].content
    assert "ValidateSet('k8s', 'docker-compose')" in by_path["install.ps1"].content
    assert "[switch]$SkipVerify" in by_path["install.ps1"].content
    assert "[switch]$SkipDryRun" in by_path["install.ps1"].content
    assert "[switch]$SkipHealthCheck" in by_path["install.ps1"].content
    assert "[switch]$SkipDiagnostics" in by_path["install.ps1"].content
    assert "[switch]$Yes" in by_path["install.ps1"].content
    assert "verify.ps1" in by_path["install.ps1"].content
    assert "Invoke-DockerComposeDryRun" in by_path["install.ps1"].content
    assert "Invoke-DockerComposeInstall" in by_path["install.ps1"].content
    assert "Invoke-Diagnostics $Mode" in by_path["install.ps1"].content
    assert "Deployment succeeded for mode: $Mode." in by_path["install.ps1"].content
    assert "docker compose --env-file" in by_path["install.ps1"].content
    assert "docker info" in by_path["install.ps1"].content
    assert "Get-ComposeEnvFile -RequireConcreteEnv" in by_path["install.ps1"].content
    assert "Test-SecretPlaceholders $envFile" in by_path["install.ps1"].content
    assert "Invoke-LoadImageArchives" in by_path["install.ps1"].content
    assert "docker load -i $archivePath" in by_path["install.ps1"].content
    assert "docker tag $image.sourceRef $image.targetRef" in by_path["install.ps1"].content
    assert "[System.Text.Encoding]::UTF8" in by_path["install.ps1"].content
    assert "ReadAllText((Join-Path $ScriptDir 'manifest.json'), [System.Text.Encoding]::UTF8)" in by_path["install.ps1"].content
    assert "ReadAllText($valuesPath, [System.Text.Encoding]::UTF8)" in by_path["install.ps1"].content
    assert "bash (Join-Path $ScriptDir 'docker-compose" not in by_path["install.ps1"].content


def test_render_root_install_files_defaults_compose_when_package_only_supports_compose() -> None:
    files = render_root_install_files({"deployModes": ["docker-compose"]})
    by_path = {item.path.as_posix(): item for item in files}

    assert 'MODE="docker-compose"' in by_path["install.sh"].content
    assert "[string]$Mode = 'docker-compose'" in by_path["install.ps1"].content
