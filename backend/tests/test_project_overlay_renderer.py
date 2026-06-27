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
