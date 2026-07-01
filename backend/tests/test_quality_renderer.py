from __future__ import annotations

from deployment_package_factory.services.deployment_packages.quality_renderer import QUALITY_GATE_VERSION, render_quality_gate_files


def test_render_quality_gate_files_exports_entries() -> None:
    files = render_quality_gate_files(
        {
            "packageId": "pkg-test",
            "projectKey": "standard-eam",
            "productVersion": "2026.06",
            "deployModes": ["k8s", "docker-compose"],
            "database": "postgres",
        }
    )
    by_path = {item.path.as_posix(): item for item in files}

    assert "quality-gate.sh" in by_path
    assert "quality-gate.ps1" in by_path
    assert "docs/quality-report.md" in by_path
    assert by_path["quality-gate.sh"].executable is True
    assert by_path["quality-gate.ps1"].executable is False
    assert f'QUALITY_GATE_VERSION="{QUALITY_GATE_VERSION}"' in by_path["quality-gate.sh"].content
    assert "k8s/dry-run.sh" in by_path["quality-gate.sh"].content
    assert "docker-compose/dry-run.sh" in by_path["quality-gate.sh"].content
    assert "quality-report.runtime.md" in by_path["quality-gate.ps1"].content
    assert "ReadAllText((Join-Path $ScriptDir 'manifest.json'), [System.Text.Encoding]::UTF8)" in by_path["quality-gate.ps1"].content
    assert "Required Checks" in by_path["docs/quality-report.md"].content
    assert "quality-report.runtime.md" in by_path["docs/quality-report.md"].content
