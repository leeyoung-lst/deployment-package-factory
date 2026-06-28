from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from deployment_package_factory.services.deployment_packages.template_paths import default_overlay_template_dir


@dataclass(frozen=True)
class RenderedOverlayFile:
    path: PurePosixPath
    content: str
    executable: bool = False


def render_project_overlay_files(manifest: dict, template_dir: Path | None = None) -> list[RenderedOverlayFile]:
    project_key = manifest.get("projectKey") or "custom"
    profile = manifest.get("projectProfile") or {}
    overlay_dir = PurePosixPath("overlays") / project_key
    values = _overlay_values(manifest, profile)
    files = [
        RenderedOverlayFile(overlay_dir / "README.md", _overlay_readme(manifest, profile)),
        RenderedOverlayFile(overlay_dir / "values.json", json.dumps(values, ensure_ascii=False, indent=2) + "\n"),
        RenderedOverlayFile(overlay_dir / "kustomization.yaml", _kustomization_stub(manifest, profile)),
    ]
    files.extend(_template_files(project_key, overlay_dir, template_dir or default_overlay_template_dir()))
    return files


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


def _template_files(project_key: str, overlay_dir: PurePosixPath, template_dir: Path) -> list[RenderedOverlayFile]:
    project_dir = (template_dir / project_key).resolve()
    template_root = template_dir.resolve()
    if not project_dir.exists():
        return []
    if not project_dir.is_dir():
        raise ValueError(f"Overlay template path must be a directory: {project_dir}")
    if not project_dir.is_relative_to(template_root):
        raise ValueError(f"Overlay template path escapes template root: {project_dir}")

    files: list[RenderedOverlayFile] = []
    for path in sorted(item for item in project_dir.rglob("*") if item.is_file()):
        relative = path.relative_to(project_dir).as_posix()
        if _has_unsafe_path_segment(relative):
            raise ValueError(f"Unsafe overlay template path: {relative}")
        files.append(
            RenderedOverlayFile(
                overlay_dir / "files" / PurePosixPath(relative),
                path.read_text(encoding="utf-8"),
                executable=path.suffix == ".sh",
            )
        )
    return files


def _has_unsafe_path_segment(path: str) -> bool:
    return any(segment in {"", ".", ".."} for segment in PurePosixPath(path).parts)
