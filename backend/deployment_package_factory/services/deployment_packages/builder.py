from __future__ import annotations

import hashlib
import json
import base64
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
from datetime import datetime, timezone
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence
from uuid import uuid4

from deployment_package_factory.services.deployment_packages.catalog import load_catalog
from deployment_package_factory.services.deployment_packages.dependency_resolver import resolve_package_preview
from deployment_package_factory.services.deployment_packages.deployment_renderer import render_deployment_files
from deployment_package_factory.services.deployment_packages.init_script_renderer import render_init_files
from deployment_package_factory.services.deployment_packages.install_renderer import INSTALLER_OPTIONS, INSTALLER_VERSION, render_root_install_files
from deployment_package_factory.services.deployment_packages.models import (
    ImageExportEnvironmentCheck,
    PackageBuildRequest,
    PackageBuildResult,
    ProjectProfile,
)
from deployment_package_factory.services.deployment_packages.kubernetes_runtime import (
    read_kubernetes_pods,
    source_env_namespaces,
)
from deployment_package_factory.services.deployment_packages.project_overlay_renderer import render_project_overlay_files
from deployment_package_factory.services.deployment_packages.quality_renderer import QUALITY_GATE_CHECKS, QUALITY_GATE_VERSION, render_quality_gate_files
from deployment_package_factory.services.deployment_packages.values_renderer import render_values_files
from deployment_package_factory.services.deployment_packages.verify_renderer import VERIFIER_VERSION, render_package_verify_files


DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[4] / "data" / "deployment-packages"
DockerRunner = Callable[[Sequence[str]], None]


class PackageBuildError(RuntimeError):
    pass


@dataclass(frozen=True)
class RuntimeSourceImage:
    source_ref: str
    image_id: str = ""
    namespace: str = ""
    pod: str = ""
    container: str = ""


def check_image_export_environment() -> ImageExportEnvironmentCheck:
    if shutil.which("skopeo"):
        try:
            version = subprocess.run(["skopeo", "--version"], check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as exc:
            detail = (exc.stderr or exc.stdout or str(exc)).strip()
            return ImageExportEnvironmentCheck(
                available=False,
                exportTool="skopeo",
                message=f"Skopeo is installed but not ready for image export: {detail}",
            )
        return ImageExportEnvironmentCheck(
            available=True,
            exportTool="skopeo",
            toolVersion=_first_line(version.stdout),
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
            exportTool="docker",
            dockerVersion=_first_line(exc.stdout),
            message=f"Docker is installed but not ready for image export: {detail}",
        )
    return ImageExportEnvironmentCheck(
        available=True,
        exportTool="docker",
        dockerVersion=_first_line(version.stdout),
        message="Docker CLI and daemon are available for image archive export.",
    )


def build_deployment_package(
    request: PackageBuildRequest,
    *,
    output_dir: Path | None = None,
    docker_runner: DockerRunner | None = None,
) -> PackageBuildResult:
    package_id = f"pkg-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:8]}"
    base_dir = output_dir or DEFAULT_OUTPUT_DIR
    work_dir = base_dir / "work" / package_id
    artifact_dir = base_dir / "artifacts"
    package_root = work_dir / f"local-ai-prod-package-{package_id}"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    package_root.mkdir(parents=True, exist_ok=True)

    catalog = load_catalog()
    request, project = _apply_project_build_defaults(request, catalog)
    preview = resolve_package_preview(request, catalog)
    image_tag = project.image_tag if project else "prod"
    runtime_images = _discover_runtime_source_images(request.source_env, preview.images, image_tag)
    image_entries = _image_entries(preview.images, request, image_tag, runtime_images, require_runtime_sources=bool(runtime_images))
    manifest = _manifest(package_id, request, preview, image_entries, project, image_tag)

    _write_text(package_root / "manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    _write_text(package_root / "README.md", _readme(manifest))
    _write_text(package_root / "docs" / "install-k8s.md", "# K8s 安装说明\n\n替换 `k8s/secrets.template.yaml` 后执行 `k8s/install.sh`。\n")
    _write_text(package_root / "docs" / "install-docker-compose.md", "# Docker Compose 安装说明\n\n根据 `.env.template` 创建 `.env` 后执行 `docker-compose/install.sh`。\n")
    for rendered_file in render_root_install_files():
        writer = _write_script if rendered_file.executable else _write_text
        writer(package_root / rendered_file.path, rendered_file.content)
    for rendered_file in render_package_verify_files():
        writer = _write_script if rendered_file.executable else _write_text
        writer(package_root / rendered_file.path, rendered_file.content)
    for rendered_file in render_quality_gate_files(manifest):
        writer = _write_script if rendered_file.executable else _write_text
        writer(package_root / rendered_file.path, rendered_file.content)
    for rendered_file in render_deployment_files(manifest):
        writer = _write_script if rendered_file.executable else _write_text
        writer(package_root / rendered_file.path, rendered_file.content)
    for rendered_file in render_init_files(manifest):
        writer = _write_script if rendered_file.executable else _write_text
        writer(package_root / rendered_file.path, rendered_file.content)
    for rendered_file in render_project_overlay_files(manifest):
        writer = _write_script if rendered_file.executable else _write_text
        writer(package_root / rendered_file.path, rendered_file.content)
    _write_text(package_root / "images" / "images.txt", _images_txt(image_entries))
    _write_text(package_root / "images" / "archives" / ".gitkeep", "")
    _write_script(package_root / "scripts" / "pull-images.sh", _pull_images_script(image_entries))
    _write_script(package_root / "scripts" / "save-images.sh", _save_images_script(image_entries))
    _write_script(package_root / "scripts" / "load-images.sh", _load_images_script(image_entries))
    image_lock = {"images": image_entries, "archives": _archive_lock(package_root)}
    _write_text(package_root / "security" / "image-digest-lock.json", json.dumps(image_lock, ensure_ascii=False, indent=2) + "\n")

    if request.image_mode == "image-archive" or request.target_profile.export_images:
        _export_image_archives(package_root, image_entries, docker_runner, source_tls_verify=not request.target_profile.source_registry_insecure)
        _write_text(
            package_root / "security" / "image-digest-lock.json",
            json.dumps({"images": image_entries, "archives": _archive_lock(package_root)}, ensure_ascii=False, indent=2) + "\n",
        )

    package_index = _package_index(package_root, manifest)
    manifest["validationSummary"] = _validation_summary(package_root, None, package_index, image_entries, request.image_mode)
    for rendered_file in render_values_files(manifest):
        writer = _write_script if rendered_file.executable else _write_text
        writer(package_root / rendered_file.path, rendered_file.content)
    package_index = _package_index(package_root, manifest)
    _write_text(package_root / "package-index.json", json.dumps(package_index, ensure_ascii=False, indent=2) + "\n")
    sha_file = package_root / "security" / "SHA256SUMS"
    _write_text(sha_file, _sha256s(package_root))

    artifact_path = artifact_dir / f"{package_root.name}.tar.gz"
    with tarfile.open(artifact_path, "w:gz") as tar:
        tar.add(package_root, arcname=package_root.name, filter=_tar_metadata_filter)
    digest = _file_sha256(artifact_path)
    checksum_path = artifact_path.with_name(f"{artifact_path.name}.sha256")
    _write_text(checksum_path, f"{digest}  {artifact_path.name}\n")

    return PackageBuildResult(
        packageId=package_id,
        workDir=str(work_dir),
        artifactPath=str(artifact_path),
        checksumPath=str(checksum_path),
        artifactSize=artifact_path.stat().st_size,
        validationSummary=_validation_summary(package_root, artifact_path, package_index, image_entries, request.image_mode),
        sha256=digest,
        manifest=manifest,
    )


def _manifest(
    package_id: str,
    request: PackageBuildRequest,
    preview,
    image_entries: list[dict],
    project: ProjectProfile | None,
    image_tag: str,
) -> dict:
    return {
        "packageId": package_id,
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "projectKey": request.project_key,
        "projectProfile": project.model_dump(by_alias=True) if project else None,
        "productVersion": request.product_version,
        "sourceEnv": request.source_env,
        "targetEnv": request.target_profile.env,
        "deployModes": request.deploy_modes,
        "database": preview.database.key,
        "databaseImage": preview.database.image,
        "imageTag": image_tag,
        "imageMode": request.image_mode,
        "platformServices": [item.key for item in preview.platform_services],
        "businessServices": [item.key for item in preview.business_services],
        "middleware": [item.key for item in preview.middleware],
        "targetProfile": request.target_profile.model_dump(by_alias=True),
        "images": preview.images,
        "imageEntries": image_entries,
    }


def _apply_project_build_defaults(request: PackageBuildRequest, catalog) -> tuple[PackageBuildRequest, ProjectProfile | None]:
    if not request.project_key:
        return request, None
    project = catalog.projects.get(request.project_key)
    if project is None:
        raise PackageBuildError(f"Unknown project {request.project_key!r}.")
    if request.product_version and request.product_version not in project.versions:
        raise PackageBuildError(f"Unsupported product version {request.product_version!r} for project {project.key!r}.")
    target = request.target_profile.model_copy(
        update={
            "env": request.target_profile.env or "prod",
            "domain": request.target_profile.domain if request.target_profile.domain != "prod.example.com" else project.domain,
            "source_registry": request.target_profile.source_registry or project.registry,
            "registry": request.target_profile.registry or project.registry,
            "namespace_prefix": request.target_profile.namespace_prefix if request.target_profile.namespace_prefix != "prod" else project.namespace_prefix,
            "storage_class": request.target_profile.storage_class or project.storage_class,
        }
    )
    return request.model_copy(
        update={
            "source_env": request.source_env or project.default_source_env,
            "deploy_modes": request.deploy_modes or project.default_deploy_modes,
            "platform_services": request.platform_services or project.default_platform_services,
            "business_services": request.business_services or project.default_business_services,
            "database": request.database or project.default_database,
            "product_version": request.product_version or project.default_version,
            "target_profile": target,
        }
    ), project


def _readme(manifest: dict) -> str:
    return f"""# Local AI 生产部署包

包编号：`{manifest["packageId"]}`

来源环境：`{manifest["sourceEnv"]}`

目标环境：`{manifest["targetEnv"]}`

部署方式：{", ".join(manifest["deployModes"]) or "-"}

数据库：`{manifest["database"]}`

安装前质量门禁：

```bash
./quality-gate.sh
```

质量报告：`docs/quality-report.md`

"""


def _image_entries(
    images: dict[str, list[str]],
    request: PackageBuildRequest,
    default_tag: str,
    runtime_images: dict[str, RuntimeSourceImage] | None = None,
    *,
    require_runtime_sources: bool = False,
) -> list[dict]:
    entries: list[dict] = []
    seen: set[str] = set()
    runtime_images = runtime_images or {}
    source_registry = request.target_profile.source_registry.strip().rstrip("/")
    registry = request.target_profile.registry.strip().rstrip("/")
    for group, values in images.items():
        for raw in values:
            catalog_ref = _with_default_tag(raw, default_tag)
            runtime_image = runtime_images.get(catalog_ref)
            source_ref = runtime_image.source_ref if runtime_image else _target_image_ref(catalog_ref, source_registry)
            source_export_ref = _source_export_ref(runtime_image) if runtime_image else source_ref
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
                "sourceRegistryInsecure": request.target_profile.source_registry_insecure,
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
                    }
                )
            elif require_runtime_sources:
                entry.update(
                    {
                        "sourceMissing": True,
                        "sourceResolvedFrom": "missing",
                        "sourceMessage": f"未在来源环境 {request.source_env} 的运行中 Pod 中匹配到镜像 {catalog_ref}",
                    }
                )
            entries.append(entry)
    return sorted(entries, key=lambda item: (item["group"], item["targetRef"]))


def _discover_runtime_source_images(source_env: str, images: dict[str, list[str]], default_tag: str) -> dict[str, RuntimeSourceImage]:
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


def _source_env_namespaces(source_env: str) -> list[str]:
    return source_env_namespaces(source_env)


def _list_runtime_images(namespaces: list[str]) -> list[RuntimeSourceImage]:
    token_path = Path(os.getenv("KUBERNETES_SERVICEACCOUNT_TOKEN_PATH", "/var/run/secrets/kubernetes.io/serviceaccount/token"))
    if not token_path.exists():
        return []
    try:
        token = token_path.read_text(encoding="utf-8").strip()
    except OSError:
        return []
    if not token:
        return []

    runtime_images: list[RuntimeSourceImage] = []
    for namespace in namespaces:
        payload = read_kubernetes_pods(namespace, token)
        for pod in payload.get("items", []):
            if pod.get("status", {}).get("phase") not in {"Pending", "Running", "Succeeded"}:
                continue
            spec_containers = {
                item.get("name", ""): item.get("image", "")
                for item in pod.get("spec", {}).get("containers", [])
                if item.get("image")
            }
            statuses = {
                item.get("name", ""): item.get("imageID", "")
                for item in pod.get("status", {}).get("containerStatuses", [])
            }
            for container, image in spec_containers.items():
                runtime_images.append(
                    RuntimeSourceImage(
                        source_ref=image,
                        image_id=_normalize_image_id(statuses.get(container, "")),
                        namespace=namespace,
                        pod=pod.get("metadata", {}).get("name", ""),
                        container=container,
                    )
                )
    return runtime_images


def _best_runtime_image(catalog_ref: str, runtime_images: list[RuntimeSourceImage]) -> RuntimeSourceImage | None:
    matches: list[tuple[tuple[int, int, str], RuntimeSourceImage]] = []
    for image in runtime_images:
        score = _runtime_image_match_score(catalog_ref, image.source_ref)
        if score <= 0:
            continue
        matches.append(((score, _image_registry_priority(image.source_ref), image.source_ref), image))
    if not matches:
        return None
    matches.sort(key=lambda item: item[0], reverse=True)
    return matches[0][1]


def _runtime_image_match_score(catalog_ref: str, runtime_ref: str) -> int:
    expected_path = _image_path_without_tag(catalog_ref)
    runtime_path = _image_path_without_tag(runtime_ref)
    expected_base = expected_path.rsplit("/", 1)[-1]
    runtime_base = runtime_path.rsplit("/", 1)[-1]
    if runtime_path == expected_path:
        return 100
    if runtime_base == expected_base:
        return 80
    if runtime_base == f"local-ai-{expected_base}":
        return 70
    if expected_base.startswith("local-ai-") and runtime_base == expected_base.removeprefix("local-ai-"):
        return 60
    return 0


def _image_path_without_tag(image: str) -> str:
    if _has_registry(image):
        image = image.split("/", 1)[1]
    image = image.split("@", 1)[0]
    last_part = image.rsplit("/", 1)[-1]
    if ":" in last_part:
        return image.rsplit(":", 1)[0]
    return image


def _image_registry_priority(image: str) -> int:
    return 1 if _has_registry(image) else 0


def _source_export_ref(runtime_image: RuntimeSourceImage | None) -> str:
    if not runtime_image:
        return ""
    if runtime_image.image_id and "@sha256:" in runtime_image.image_id:
        return runtime_image.image_id
    return runtime_image.source_ref


def _normalize_image_id(image_id: str) -> str:
    for prefix in ("docker-pullable://", "containerd://", "docker://"):
        if image_id.startswith(prefix):
            return image_id.removeprefix(prefix)
    return image_id


def _with_default_tag(image: str, default_tag: str) -> str:
    image = image.strip()
    if not image:
        raise PackageBuildError("Image reference cannot be empty.")
    last_part = image.rsplit("/", 1)[-1]
    if ":" in last_part or "@" in last_part:
        return image
    return f"{image}:{default_tag}"


def _target_image_ref(source_ref: str, registry: str) -> str:
    if not registry:
        return source_ref
    if _has_registry(source_ref):
        image_path = source_ref.split("/", 1)[1]
    else:
        image_path = source_ref
    return f"{registry}/{image_path}"


def _has_registry(image: str) -> bool:
    if "/" not in image:
        return False
    first = image.split("/", 1)[0]
    return "." in first or ":" in first or first == "localhost"


def _safe_image_filename(image: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", image).strip("_")


def _images_txt(image_entries: list[dict]) -> str:
    lines = ["# group sourceRef targetRef archiveFile"]
    lines.extend(
        f"{item['group']} {item['sourceRef']} {item['targetRef']} {item['archiveFile']}"
        for item in image_entries
    )
    return "\n".join(lines) + "\n"


def _pull_images_script(image_entries: list[dict]) -> str:
    commands = ["#!/usr/bin/env bash", "set -euo pipefail", ""]
    commands.extend(f"docker pull {item['sourceRef']}" for item in image_entries)
    return "\n".join(commands) + "\n"


def _save_images_script(image_entries: list[dict]) -> str:
    commands = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        "mkdir -p images/archives",
        "",
    ]
    commands.extend(
        f"docker save -o images/archives/{item['archiveFile']} {item['sourceRef']}"
        for item in image_entries
    )
    return "\n".join(commands) + "\n"


def _load_images_script(image_entries: list[dict]) -> str:
    commands = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        'SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"',
        'PACKAGE_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"',
        "",
    ]
    for item in image_entries:
        archive = f"${{PACKAGE_ROOT}}/images/archives/{item['archiveFile']}"
        commands.append(f"docker load -i {archive}")
        if item["sourceRef"] != item["targetRef"]:
            commands.append(f"docker tag {item['sourceRef']} {item['targetRef']}")
    return "\n".join(commands) + "\n"


def _export_image_archives(
    package_root: Path,
    image_entries: list[dict],
    docker_runner: DockerRunner | None = None,
    *,
    source_tls_verify: bool = True,
) -> None:
    archive_dir = package_root / "images" / "archives"
    archive_dir.mkdir(parents=True, exist_ok=True)
    if docker_runner is None:
        _preflight_source_images(image_entries, source_tls_verify=source_tls_verify)
    for item in image_entries:
        source_ref = item["sourceRef"]
        source_export_ref = item.get("sourceExportRef") or source_ref
        archive_path = archive_dir / item["archiveFile"]
        try:
            if docker_runner is not None:
                docker_runner(["docker", "pull", source_ref])
                docker_runner(["docker", "save", "-o", str(archive_path), source_ref])
            else:
                _run_image_export(source_ref, archive_path, source_export_ref=source_export_ref, source_tls_verify=source_tls_verify)
        except Exception as exc:
            raise PackageBuildError(f"Image export failed for {source_ref}: {exc}") from exc


def _run_image_export(
    source_ref: str,
    archive_path: Path,
    *,
    source_export_ref: str = "",
    source_tls_verify: bool = True,
) -> None:
    export_ref = source_export_ref or source_ref
    if shutil.which("skopeo"):
        _run_skopeo(export_ref, archive_path, archive_ref=source_ref, source_tls_verify=source_tls_verify)
        return
    _run_docker(["docker", "pull", source_ref])
    _run_docker(["docker", "save", "-o", str(archive_path), source_ref])


def _run_skopeo(source_ref: str, archive_path: Path, *, archive_ref: str = "", source_tls_verify: bool = True) -> None:
    command = ["skopeo", "copy", f"docker://{source_ref}", f"docker-archive:{archive_path}:{archive_ref or source_ref}"]
    if not source_tls_verify:
        command.insert(2, "--src-tls-verify=false")
    authfile = _source_registry_authfile(source_ref)
    if authfile:
        command[2:2] = ["--src-authfile", authfile]
    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise PackageBuildError("Skopeo is not available.") from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or str(exc)).strip()
        raise PackageBuildError(detail) from exc
    finally:
        if authfile:
            Path(authfile).unlink(missing_ok=True)


def _preflight_source_images(image_entries: list[dict], *, source_tls_verify: bool = True) -> None:
    if not shutil.which("skopeo"):
        return
    failures: list[str] = []
    for item in image_entries:
        if item.get("sourceMissing"):
            failures.append(f"{item.get('catalogRef')}: {item.get('sourceMessage') or 'runtime source image is missing'}")
            continue
        source_ref = item.get("sourceExportRef") or item["sourceRef"]
        try:
            _run_skopeo_inspect(source_ref, source_tls_verify=source_tls_verify)
        except PackageBuildError as exc:
            failures.append(f"{source_ref}: {exc}")
    if failures:
        details = "; ".join(failures)
        raise PackageBuildError(f"Source image preflight failed. Missing or inaccessible images: {details}")


def _run_skopeo_inspect(source_ref: str, *, source_tls_verify: bool = True) -> None:
    command = ["skopeo", "inspect", f"docker://{source_ref}"]
    if not source_tls_verify:
        command.insert(2, "--tls-verify=false")
    authfile = _source_registry_authfile(source_ref)
    if authfile:
        command[2:2] = ["--authfile", authfile]
    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise PackageBuildError("Skopeo is not available.") from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or str(exc)).strip()
        raise PackageBuildError(detail) from exc
    finally:
        if authfile:
            Path(authfile).unlink(missing_ok=True)


def _run_docker(command: Sequence[str]) -> None:
    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise PackageBuildError("Docker CLI is not available.") from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or str(exc)).strip()
        raise PackageBuildError(detail) from exc


def _first_line(value: str) -> str:
    return next((line.strip() for line in value.splitlines() if line.strip()), "")


def _source_registry_authfile(source_ref: str) -> str:
    username = os.getenv("DEPLOYMENT_PACKAGE_SOURCE_REGISTRY_USERNAME", "").strip()
    password = os.getenv("DEPLOYMENT_PACKAGE_SOURCE_REGISTRY_PASSWORD", "")
    registry = _source_registry_host(source_ref)
    if not username or not password or not registry:
        return ""
    auth = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
    payload = {"auths": {registry: {"auth": auth}}}
    handle = tempfile.NamedTemporaryFile("w", encoding="utf-8", prefix="skopeo-source-auth-", suffix=".json", delete=False)
    with handle:
        json.dump(payload, handle)
    return handle.name


def _source_registry_host(source_ref: str) -> str:
    if not _has_registry(source_ref):
        return ""
    return source_ref.split("/", 1)[0]


def _archive_lock(package_root: Path) -> list[dict]:
    archive_dir = package_root / "images" / "archives"
    if not archive_dir.exists():
        return []
    result = []
    for path in sorted(item for item in archive_dir.iterdir() if item.is_file() and item.name != ".gitkeep"):
        result.append({"file": path.name, "sha256": _file_sha256(path), "size": path.stat().st_size})
    return result


def _validation_summary(
    package_root: Path,
    artifact_path: Path | None,
    package_index: dict,
    image_entries: list[dict],
    image_mode: str,
) -> dict:
    archive_dir = package_root / "images" / "archives"
    archive_files = {
        path.name
        for path in archive_dir.iterdir()
        if path.is_file() and path.name != ".gitkeep"
    } if archive_dir.exists() else set()
    expected_archives = {item["archiveFile"] for item in image_entries} if image_mode == "image-archive" else set()
    return {
        "artifactSize": artifact_path.stat().st_size if artifact_path and artifact_path.exists() else 0,
        "packageIndexFileCount": package_index.get("summary", {}).get("fileCount", 0),
        "packageIndexTotalBytes": package_index.get("summary", {}).get("totalBytes", 0),
        "imageEntryCount": len(image_entries),
        "imageArchiveCount": len(archive_files),
        "missingImageArchiveCount": len(expected_archives - archive_files),
    }


def _package_index(package_root: Path, manifest: dict) -> dict:
    files = [_file_index_entry(path, package_root) for path in sorted(item for item in package_root.rglob("*") if item.is_file())]
    return {
        "schemaVersion": "deployment-package-index/v1",
        "packageId": manifest["packageId"],
        "projectKey": manifest.get("projectKey") or "custom",
        "productVersion": manifest.get("productVersion") or "",
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "fileCount": len(files),
            "totalBytes": sum(item["size"] for item in files),
            "deployModes": manifest["deployModes"],
            "imageMode": manifest["imageMode"],
            "database": manifest["database"],
        },
        "installer": {
            "version": INSTALLER_VERSION,
            "entrypoints": ["install.sh", "install.ps1"],
            "supportedModes": ["k8s", "docker-compose"],
            "options": INSTALLER_OPTIONS,
        },
        "verifier": {
            "version": VERIFIER_VERSION,
            "entrypoints": ["verify.sh", "verify.ps1"],
            "checks": ["required-files", "sha256sums", "package-index", "image-archive-lock"],
        },
        "qualityGate": {
            "version": QUALITY_GATE_VERSION,
            "entrypoints": ["quality-gate.sh", "quality-gate.ps1"],
            "checks": QUALITY_GATE_CHECKS,
            "report": "docs/quality-report.runtime.md",
            "template": "docs/quality-report.md",
        },
        "sections": {
            "root": _section(
                files,
                {
                    "README.md",
                    "manifest.json",
                    "package-index.json",
                    "install.sh",
                    "install.ps1",
                    "verify.sh",
                    "verify.ps1",
                    "quality-gate.sh",
                    "quality-gate.ps1",
                    "deploy-values.json",
                },
            ),
            "docs": _section_prefix(files, "docs/"),
            "k8s": _section_prefix(files, "k8s/"),
            "dockerCompose": _section_prefix(files, "docker-compose/"),
            "init": _section_prefix(files, "init/"),
            "overlays": _section_prefix(files, "overlays/"),
            "images": _section_prefix(files, "images/"),
            "scripts": _section_prefix(files, "scripts/"),
            "security": _section_prefix(files, "security/"),
        },
    }


def _file_index_entry(path: Path, package_root: Path) -> dict:
    rel = path.relative_to(package_root).as_posix()
    return {
        "path": rel,
        "size": path.stat().st_size,
        "sha256": _file_sha256(path),
        "executable": path.suffix == ".sh",
    }


def _section(files: list[dict], paths: set[str]) -> list[dict]:
    return [item for item in files if item["path"] in paths]


def _section_prefix(files: list[dict], prefix: str) -> list[dict]:
    return [item for item in files if item["path"].startswith(prefix)]


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_script(path: Path, content: str) -> None:
    _write_text(path, content)
    path.chmod(0o755)


def _tar_metadata_filter(info: tarfile.TarInfo) -> tarfile.TarInfo:
    if info.isfile() and info.name.endswith(".sh"):
        info.mode = 0o755
    return info


def _sha256s(root: Path) -> str:
    lines = []
    for path in sorted(item for item in root.rglob("*") if item.is_file() and item.name != "SHA256SUMS"):
        rel = path.relative_to(root).as_posix()
        lines.append(f"{_file_sha256(path)}  {rel}")
    return "\n".join(lines) + "\n"


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
