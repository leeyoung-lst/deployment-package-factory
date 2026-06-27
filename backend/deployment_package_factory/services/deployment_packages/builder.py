from __future__ import annotations

import hashlib
import json
import re
import subprocess
import tarfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Sequence
from uuid import uuid4

from deployment_package_factory.services.deployment_packages.catalog import load_catalog
from deployment_package_factory.services.deployment_packages.dependency_resolver import resolve_package_preview
from deployment_package_factory.services.deployment_packages.deployment_renderer import render_deployment_files
from deployment_package_factory.services.deployment_packages.init_script_renderer import render_init_files
from deployment_package_factory.services.deployment_packages.install_renderer import INSTALLER_OPTIONS, INSTALLER_VERSION, render_root_install_files
from deployment_package_factory.services.deployment_packages.models import PackageBuildRequest, PackageBuildResult, ProjectProfile
from deployment_package_factory.services.deployment_packages.project_overlay_renderer import render_project_overlay_files


DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[4] / "data" / "deployment-packages"
DockerRunner = Callable[[Sequence[str]], None]


class PackageBuildError(RuntimeError):
    pass


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
    image_entries = _image_entries(preview.images, request, image_tag)
    manifest = _manifest(package_id, request, preview, image_entries, project, image_tag)

    _write_text(package_root / "manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    _write_text(package_root / "README.md", _readme(manifest))
    _write_text(package_root / "docs" / "install-k8s.md", "# K8s 安装说明\n\n替换 `k8s/secrets.template.yaml` 后执行 `k8s/install.sh`。\n")
    _write_text(package_root / "docs" / "install-docker-compose.md", "# Docker Compose 安装说明\n\n根据 `.env.template` 创建 `.env` 后执行 `docker-compose/install.sh`。\n")
    for rendered_file in render_root_install_files():
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
        _export_image_archives(package_root, image_entries, docker_runner or _run_docker)
        _write_text(
            package_root / "security" / "image-digest-lock.json",
            json.dumps({"images": image_entries, "archives": _archive_lock(package_root)}, ensure_ascii=False, indent=2) + "\n",
        )

    _write_text(package_root / "package-index.json", json.dumps(_package_index(package_root, manifest), ensure_ascii=False, indent=2) + "\n")
    sha_file = package_root / "security" / "SHA256SUMS"
    _write_text(sha_file, _sha256s(package_root))

    artifact_path = artifact_dir / f"{package_root.name}.tar.gz"
    with tarfile.open(artifact_path, "w:gz") as tar:
        tar.add(package_root, arcname=package_root.name, filter=_tar_metadata_filter)
    digest = _file_sha256(artifact_path)

    return PackageBuildResult(
        packageId=package_id,
        workDir=str(work_dir),
        artifactPath=str(artifact_path),
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

"""


def _image_entries(images: dict[str, list[str]], request: PackageBuildRequest, default_tag: str) -> list[dict]:
    entries: list[dict] = []
    seen: set[str] = set()
    registry = request.target_profile.registry.strip().rstrip("/")
    for group, values in images.items():
        for raw in values:
            source_ref = _with_default_tag(raw, default_tag)
            target_ref = _target_image_ref(source_ref, registry)
            if target_ref in seen:
                continue
            seen.add(target_ref)
            entries.append(
                {
                    "group": group,
                    "sourceRef": source_ref,
                    "targetRef": target_ref,
                    "archiveFile": f"{_safe_image_filename(target_ref)}.tar",
                }
            )
    return sorted(entries, key=lambda item: (item["group"], item["targetRef"]))


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


def _export_image_archives(package_root: Path, image_entries: list[dict], docker_runner: DockerRunner) -> None:
    archive_dir = package_root / "images" / "archives"
    archive_dir.mkdir(parents=True, exist_ok=True)
    for item in image_entries:
        source_ref = item["sourceRef"]
        archive_path = archive_dir / item["archiveFile"]
        try:
            docker_runner(["docker", "pull", source_ref])
            docker_runner(["docker", "save", "-o", str(archive_path), source_ref])
        except Exception as exc:
            raise PackageBuildError(f"Image export failed for {source_ref}: {exc}") from exc


def _run_docker(command: Sequence[str]) -> None:
    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise PackageBuildError("Docker CLI is not available.") from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or str(exc)).strip()
        raise PackageBuildError(detail) from exc


def _archive_lock(package_root: Path) -> list[dict]:
    archive_dir = package_root / "images" / "archives"
    if not archive_dir.exists():
        return []
    result = []
    for path in sorted(item for item in archive_dir.iterdir() if item.is_file() and item.name != ".gitkeep"):
        result.append({"file": path.name, "sha256": _file_sha256(path), "size": path.stat().st_size})
    return result


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
        "sections": {
            "root": _section(files, {"README.md", "manifest.json", "package-index.json", "install.sh", "install.ps1"}),
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
