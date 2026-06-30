from __future__ import annotations

from deployment_package_factory.services.deployment_packages.verify_renderer import render_package_verify_files


def test_render_package_verify_files_exports_shell_and_powershell_entries() -> None:
    files = render_package_verify_files()
    by_path = {item.path.as_posix(): item for item in files}

    assert "verify.sh" in by_path
    assert "verify.ps1" in by_path
    assert by_path["verify.sh"].executable is True
    assert by_path["verify.ps1"].executable is False
    assert 'VERIFIER_VERSION="1.0.0"' in by_path["verify.sh"].content
    assert "sha256sum -c" in by_path["verify.sh"].content
    assert "SHA_CHECK_FILE" in by_path["verify.sh"].content
    assert "package-index.json" in by_path["verify.sh"].content
    assert "quality-gate.sh" in by_path["verify.sh"].content
    assert "docs/quality-report.md" in by_path["verify.sh"].content
    assert "image-digest-lock.json" in by_path["verify.sh"].content
    assert "image archive is not locked" in by_path["verify.sh"].content
    assert "SHA256SUMS file set mismatch" in by_path["verify.sh"].content
    assert "package-index file set mismatch" in by_path["verify.sh"].content
    assert "$VerifierVersion = '1.0.0'" in by_path["verify.ps1"].content
    assert "Get-FileHash -Algorithm SHA256" in by_path["verify.ps1"].content
    assert "[System.Security.Cryptography.SHA256]::Create()" in by_path["verify.ps1"].content
    assert "[System.Text.Encoding]::UTF8" in by_path["verify.ps1"].content
    assert "Read-Utf8Text (Join-Path $ScriptDir 'manifest.json')" in by_path["verify.ps1"].content
    assert "ConvertFrom-Json" in by_path["verify.ps1"].content
    assert "quality-gate.ps1" in by_path["verify.ps1"].content
    assert "docker-compose/.env" in by_path["verify.ps1"].content
    assert "docs/quality-report.runtime.md" in by_path["verify.ps1"].content
    assert "SHA256SUMS file set mismatch" in by_path["verify.ps1"].content
    assert "package-index file set mismatch" in by_path["verify.ps1"].content
