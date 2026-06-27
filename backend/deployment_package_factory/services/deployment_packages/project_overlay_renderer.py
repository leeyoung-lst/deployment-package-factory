from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import PurePosixPath


@dataclass(frozen=True)
class RenderedOverlayFile:
    path: PurePosixPath
    content: str
    executable: bool = False


def render_project_overlay_files(manifest: dict) -> list[RenderedOverlayFile]:
    project_key = manifest.get("projectKey") or "custom"
    profile = manifest.get("projectProfile") or {}
    overlay_dir = PurePosixPath("overlays") / project_key
    values = _overlay_values(manifest, profile)
    return [
        RenderedOverlayFile(overlay_dir / "README.md", _overlay_readme(manifest, profile)),
        RenderedOverlayFile(overlay_dir / "values.json", json.dumps(values, ensure_ascii=False, indent=2) + "\n"),
        RenderedOverlayFile(overlay_dir / "kustomization.yaml", _kustomization_stub(manifest, profile)),
    ]


def _overlay_values(manifest: dict, profile: dict) -> dict:
    target = manifest["targetProfile"]
    return {
        "projectKey": manifest.get("projectKey") or "custom",
        "productVersion": manifest.get("productVersion") or "",
        "imageTag": manifest.get("imageTag") or "prod",
        "overlays": profile.get("overlays") or [],
        "targetProfile": {
            "domain": target.get("domain"),
            "namespacePrefix": target.get("namespacePrefix"),
            "registry": target.get("registry"),
            "storageClass": target.get("storageClass"),
        },
        "platformServices": manifest["platformServices"],
        "businessServices": manifest["businessServices"],
        "middleware": manifest["middleware"],
        "database": manifest["database"],
    }


def _overlay_readme(manifest: dict, profile: dict) -> str:
    overlays = ", ".join(profile.get("overlays") or []) or "-"
    return (
        f"# Project Overlay: {manifest.get('projectKey') or 'custom'}\n\n"
        f"Product version: `{manifest.get('productVersion') or '-'}`\n\n"
        f"Image tag: `{manifest.get('imageTag') or 'prod'}`\n\n"
        f"Overlay labels: {overlays}\n\n"
        "This directory contains project-level deployment values. Replace or extend these files with project-specific SQL, BPMN, bucket, collection, and kustomize patches when producing a hardened delivery package.\n"
    )


def _kustomization_stub(manifest: dict, profile: dict) -> str:
    labels = profile.get("overlays") or []
    label_lines = "".join(f"  local-ai/overlay-{item}: \"true\"\n" for item in labels)
    if not label_lines:
        label_lines = "  local-ai/overlay: custom\n"
    return (
        "apiVersion: kustomize.config.k8s.io/v1beta1\n"
        "kind: Kustomization\n"
        "resources:\n"
        "  - ../../k8s\n"
        "commonLabels:\n"
        f"  local-ai/project: {manifest.get('projectKey') or 'custom'}\n"
        f"{label_lines}"
    )
