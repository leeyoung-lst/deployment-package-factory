from __future__ import annotations

import json

from deployment_package_factory.services.deployment_packages.project_overlay_renderer import render_project_overlay_files


def test_render_project_overlay_files_exports_project_values() -> None:
    files = render_project_overlay_files(_manifest())
    by_path = {item.path.as_posix(): item.content for item in files}

    assert "overlays/mes-lite/README.md" in by_path
    assert "overlays/mes-lite/values.json" in by_path
    assert "overlays/mes-lite/kustomization.yaml" in by_path

    values = json.loads(by_path["overlays/mes-lite/values.json"])
    assert values["projectKey"] == "mes-lite"
    assert values["imageTag"] == "2026.06-lite"
    assert values["overlays"] == ["lite"]
    assert values["targetProfile"]["namespacePrefix"] == "mes-prod"
    assert "local-ai/overlay-lite" in by_path["overlays/mes-lite/kustomization.yaml"]


def test_render_project_overlay_files_copies_project_templates(tmp_path) -> None:
    project_dir = tmp_path / "mes-lite"
    (project_dir / "init" / "dm").mkdir(parents=True)
    (project_dir / "scripts").mkdir()
    (project_dir / "init" / "dm" / "010_project.sql").write_text("-- project sql\n", encoding="utf-8")
    (project_dir / "scripts" / "bootstrap.sh").write_text("#!/usr/bin/env bash\necho bootstrap\n", encoding="utf-8")

    files = render_project_overlay_files(_manifest(), template_dir=tmp_path)
    by_path = {item.path.as_posix(): item for item in files}

    assert by_path["overlays/mes-lite/files/init/dm/010_project.sql"].content == "-- project sql\n"
    assert by_path["overlays/mes-lite/files/scripts/bootstrap.sh"].executable is True


def test_default_overlay_template_dir_contains_mes_lite_files() -> None:
    files = render_project_overlay_files(_manifest())
    paths = {item.path.as_posix() for item in files}

    assert "overlays/mes-lite/files/init/dm/010_mes_lite_schema.sql" in paths
    assert "overlays/mes-lite/files/init/qdrant/collections.json" in paths
    assert "overlays/mes-lite/files/k8s/patches/mes-lite-resources.yaml" in paths


def _manifest() -> dict:
    return {
        "projectKey": "mes-lite",
        "projectProfile": {"overlays": ["lite"]},
        "productVersion": "2026.06",
        "imageTag": "2026.06-lite",
        "targetProfile": {
            "domain": "mes.example.com",
            "namespacePrefix": "mes-prod",
            "registry": "harbor.example.com/mes",
            "storageClass": "fast-ssd",
        },
        "platformServices": ["iam", "gateway-frontend"],
        "businessServices": ["mes"],
        "middleware": ["dm", "redis"],
        "database": "dm",
    }
