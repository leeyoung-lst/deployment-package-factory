"""Image management for deployment package builder.

This module handles image export environment checks, runtime image discovery,
and image entry generation for deployment packages.
"""
from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass

from deployment_package_factory.services.deployment_packages.models import ImageExportEnvironmentCheck, PackageBuildRequest
from deployment_package_factory.services.deployment_packages.image_version_manager import (
    inspect_image,
    ImageMetadata,
    extract_version_from_tag,
    format_size,
)


@dataclass(frozen=True)
class RuntimeSourceImage:
    """Runtime image metadata from Kubernetes pods."""
    source_ref: str
    image_id: str = ""
    namespace: str = ""
    pod: str = ""
    container: str = ""
    node: str = ""


def check_image_export_environment() -> ImageExportEnvironmentCheck:
    """Check available image export tools (skopeo or docker)."""
    if shutil.which("skopeo"):
        try:
            version = subprocess.run(["skopeo", "--version"], check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as exc:
            detail = (exc.stderr or exc.stdout or str(exc)).strip()
            return ImageExportEnvironmentCheck(
                available=False,
                export_tool="skopeo",
                message=f"Skopeo is installed but not ready for image export: {detail}",
            )
        return ImageExportEnvironmentCheck(
            available=True,
            export_tool="skopeo",
            tool_version=_first_line(version.stdout),
            message="Skopeo is available for daemonless image archive export in Kubernetes.",
        )
    try:
        version = subprocess.run(["docker", "--version"], check=True, capture_output=True, text=True)
        subprocess.run(["docker", "info"], check=True, capture_output=True, text=True)
    except FileNotFoundError:
        return ImageExportEnvironmentCheck(
            available=False,
            message="No image export tool is available. Install skopeo in the worker image, or provide Docker CLI with daemon access for local deployments.",
        )
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or str(exc)).strip()
        return ImageExportEnvironmentCheck(
            available=False,
            export_tool="docker",
            docker_version=_first_line(exc.stdout),
            message=f"Docker is installed but not ready for image export: {detail}",
        )
    return ImageExportEnvironmentCheck(
        available=True,
        export_tool="docker",
        docker_version=_first_line(version.stdout),
        message="Docker CLI and daemon are available for image archive export.",
    )


def generate_image_entries(
    images: dict[str, list[str]],
    request: PackageBuildRequest,
    default_tag: str,
    runtime_images: dict[str, RuntimeSourceImage] | None = None,
    *,
    require_runtime_sources: bool = False,
) -> list[dict]:
    """Generate image entry metadata for deployment package."""
    from deployment_package_factory.services.deployment_packages.builder import (
        _with_default_tag,
        _runtime_source_ref,
        _source_image_ref,
        _source_export_ref,
        _target_image_ref,
        _source_registry_insecure,
        _safe_image_filename,
    )

    entries: list[dict] = []
    seen: set[str] = set()
    runtime_images = runtime_images or {}
    source_registry = request.target_profile.source_registry.strip().rstrip("/")
    registry = request.target_profile.registry.strip().rstrip("/")

    for group, values in images.items():
        for raw in values:
            catalog_ref = _with_default_tag(raw, default_tag)
            runtime_image = runtime_images.get(catalog_ref)
            source_ref = _runtime_source_ref(catalog_ref, runtime_image) if runtime_image else _source_image_ref(catalog_ref, source_registry)
            source_export_ref = _source_export_ref(runtime_image, source_ref) if runtime_image else source_ref
            target_ref = _target_image_ref(catalog_ref, registry)

            if target_ref in seen:
                continue
            seen.add(target_ref)

            entry = {
                "group": group,
                "catalogRef": catalog_ref,
                "sourceRef": source_ref,
                "sourceExportRef": source_export_ref,
                "targetRef": target_ref,
                "sourceRegistryInsecure": _source_registry_insecure(source_export_ref, request.target_profile.source_registry_insecure),
                "archiveFile": f"{_safe_image_filename(target_ref)}.tar",
            }

            if runtime_image:
                entry.update(
                    {
                        "sourceResolvedFrom": "kubernetes",
                        "sourceImageId": runtime_image.image_id,
                        "sourceNamespace": runtime_image.namespace,
                        "sourcePod": runtime_image.pod,
                        "sourceContainer": runtime_image.container,
                        "sourceNode": runtime_image.node,
                    }
                )
            elif require_runtime_sources and group != "support":
                entry.update(
                    {
                        "sourceMissing": True,
                        "sourceResolvedFrom": "missing",
                        "sourceMessage": f"未在来源环境 {request.source_env} 的运行中 Pod 中匹配到镜像 {catalog_ref}",
                    }
                )
            entries.append(entry)

    return sorted(entries, key=lambda item: (item["group"], item["targetRef"]))


def discover_runtime_source_images(
    source_env: str,
    images: dict[str, list[str]],
    default_tag: str,
    business_namespaces: list[str] | None = None,
) -> dict[str, RuntimeSourceImage]:
    """Discover images from running pods in Kubernetes."""
    from deployment_package_factory.services.deployment_packages.builder import (
        _source_env_namespaces,
        _list_runtime_images,
        _with_default_tag,
        _best_runtime_image,
    )

    try:
        namespaces = _source_env_namespaces(source_env, business_namespaces)
    except TypeError:
        namespaces = _source_env_namespaces(source_env)

    if not namespaces:
        return {}

    runtime_images = _list_runtime_images(namespaces)
    if not runtime_images:
        return {}

    resolved: dict[str, RuntimeSourceImage] = {}
    for values in images.values():
        for raw in values:
            catalog_ref = _with_default_tag(raw, default_tag)
            match = _best_runtime_image(catalog_ref, runtime_images)
            if match:
                resolved[catalog_ref] = match
    return resolved


def discover_runtime_business_images(source_env: str, business_namespaces: list[str] | None = None) -> list[RuntimeSourceImage]:
    """Discover business images from running pods in business namespaces."""
    from deployment_package_factory.services.deployment_packages.builder import (
        _source_env_namespaces,
        _list_runtime_images,
    )

    if not business_namespaces:
        return []

    try:
        namespaces = _source_env_namespaces(source_env, business_namespaces)
    except TypeError:
        namespaces = _source_env_namespaces(source_env)

    business_namespace_set = set(business_namespaces)
    resolved_namespaces = [namespace for namespace in namespaces if namespace in business_namespace_set]

    if not resolved_namespaces:
        return []

    return _list_runtime_images(resolved_namespaces)


def _first_line(text: str) -> str:
    """Extract first non-empty line from text."""
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return ""
