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
from deployment_package_factory.services.deployment_packages.models import PackageBuildRequest, PackageBuildResult


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
    preview = resolve_package_preview(request, catalog)
    image_entries = _image_entries(preview.images, request)
    manifest = _manifest(package_id, request, preview, image_entries)

    _write_text(package_root / "manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    _write_text(package_root / "README.md", _readme(manifest))
    _write_text(package_root / "docs" / "install-k8s.md", "# K8s 安装说明\n\n执行 `k8s/install.sh`。\n")
    _write_text(package_root / "docs" / "install-docker-compose.md", "# Docker Compose 安装说明\n\n执行 `docker-compose/install.sh`。\n")
    _write_text(package_root / "k8s" / "namespaces.yaml", _k8s_namespaces(manifest))
    _write_text(package_root / "k8s" / "install.sh", "#!/usr/bin/env bash\nset -euo pipefail\nkubectl apply -f k8s/namespaces.yaml\n")
    _write_text(package_root / "docker-compose" / "docker-compose.yml", _compose_stub(manifest))
    _write_text(package_root / "docker-compose" / ".env.template", _env_template(manifest))
    _write_text(package_root / "scripts" / "check-prerequisites.sh", "#!/usr/bin/env bash\nset -euo pipefail\necho \"check prerequisites\"\n")
    _write_text(package_root / "images" / "images.txt", _images_txt(image_entries))
    _write_text(package_root / "images" / "archives" / ".gitkeep", "")
    _write_text(package_root / "scripts" / "pull-images.sh", _pull_images_script(image_entries))
    _write_text(package_root / "scripts" / "save-images.sh", _save_images_script(image_entries))
    _write_text(package_root / "scripts" / "load-images.sh", _load_images_script(image_entries))
    image_lock = {"images": image_entries, "archives": _archive_lock(package_root)}
    _write_text(package_root / "security" / "image-digest-lock.json", json.dumps(image_lock, ensure_ascii=False, indent=2) + "\n")

    if request.image_mode == "image-archive" or request.target_profile.export_images:
        _export_image_archives(package_root, image_entries, docker_runner or _run_docker)
        _write_text(
            package_root / "security" / "image-digest-lock.json",
            json.dumps({"images": image_entries, "archives": _archive_lock(package_root)}, ensure_ascii=False, indent=2) + "\n",
        )

    sha_file = package_root / "security" / "SHA256SUMS"
    _write_text(sha_file, _sha256s(package_root))

    artifact_path = artifact_dir / f"{package_root.name}.tar.gz"
    with tarfile.open(artifact_path, "w:gz") as tar:
        tar.add(package_root, arcname=package_root.name)
    digest = _file_sha256(artifact_path)

    return PackageBuildResult(
        packageId=package_id,
        workDir=str(work_dir),
        artifactPath=str(artifact_path),
        sha256=digest,
        manifest=manifest,
    )


def _manifest(package_id: str, request: PackageBuildRequest, preview, image_entries: list[dict]) -> dict:
    return {
        "packageId": package_id,
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "sourceEnv": request.source_env,
        "targetEnv": request.target_profile.env,
        "deployModes": request.deploy_modes,
        "database": preview.database.key,
        "imageMode": request.image_mode,
        "platformServices": [item.key for item in preview.platform_services],
        "businessServices": [item.key for item in preview.business_services],
        "middleware": [item.key for item in preview.middleware],
        "targetProfile": request.target_profile.model_dump(by_alias=True),
        "images": preview.images,
        "imageEntries": image_entries,
    }


def _readme(manifest: dict) -> str:
    return f"""# Local AI 生产部署包

包编号：`{manifest["packageId"]}`

来源环境：`{manifest["sourceEnv"]}`

目标环境：`{manifest["targetEnv"]}`

部署方式：{", ".join(manifest["deployModes"]) or "-"}

数据库：`{manifest["database"]}`

"""


def _k8s_namespaces(manifest: dict) -> str:
    prefix = manifest["targetProfile"].get("namespacePrefix") or "prod"
    namespaces = [f"{prefix}-base-public", f"{prefix}-middleware"]
    namespaces.extend(f"{prefix}-business-{item}" for item in manifest["businessServices"])
    docs = []
    for namespace in namespaces:
        docs.append(
            "apiVersion: v1\n"
            "kind: Namespace\n"
            "metadata:\n"
            f"  name: {namespace}\n"
            "  labels:\n"
            f"    local-ai/env: {prefix}\n"
        )
    return "---\n".join(docs)


def _compose_stub(manifest: dict) -> str:
    return """services:
  frontend:
    image: ${REGISTRY}/local-ai-frontend:${IMAGE_TAG}
    ports:
      - "${FRONTEND_PORT}:80"
networks:
  base-public:
  middleware:
"""


def _env_template(manifest: dict) -> str:
    registry = manifest["targetProfile"].get("registry") or "harbor.example.com/local-ai"
    return (
        f"REGISTRY={registry}\n"
        "IMAGE_TAG=prod\n"
        "FRONTEND_PORT=80\n"
        "DATABASE_PASSWORD=__REPLACE_WITH_DATABASE_PASSWORD__\n"
        "REDIS_PASSWORD=__REPLACE_WITH_REDIS_PASSWORD__\n"
    )


def _image_entries(images: dict[str, list[str]], request: PackageBuildRequest) -> list[dict]:
    entries: list[dict] = []
    seen: set[str] = set()
    registry = request.target_profile.registry.strip().rstrip("/")
    for group, values in images.items():
        for raw in values:
            source_ref = _with_default_tag(raw)
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


def _with_default_tag(image: str) -> str:
    image = image.strip()
    if not image:
        raise PackageBuildError("Image reference cannot be empty.")
    last_part = image.rsplit("/", 1)[-1]
    if ":" in last_part or "@" in last_part:
        return image
    return f"{image}:prod"


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


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


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
