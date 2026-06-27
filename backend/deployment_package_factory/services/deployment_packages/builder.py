from __future__ import annotations

import hashlib
import json
import tarfile
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from deployment_package_factory.services.deployment_packages.catalog import load_catalog
from deployment_package_factory.services.deployment_packages.dependency_resolver import resolve_package_preview
from deployment_package_factory.services.deployment_packages.models import PackageBuildRequest, PackageBuildResult


DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[4] / "data" / "deployment-packages"


def build_deployment_package(
    request: PackageBuildRequest,
    *,
    output_dir: Path | None = None,
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
    manifest = _manifest(package_id, request, preview)

    _write_text(package_root / "manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    _write_text(package_root / "README.md", _readme(manifest))
    _write_text(package_root / "docs" / "install-k8s.md", "# K8s 安装说明\n\n执行 `k8s/install.sh`。\n")
    _write_text(package_root / "docs" / "install-docker-compose.md", "# Docker Compose 安装说明\n\n执行 `docker-compose/install.sh`。\n")
    _write_text(package_root / "k8s" / "namespaces.yaml", _k8s_namespaces(manifest))
    _write_text(package_root / "k8s" / "install.sh", "#!/usr/bin/env bash\nset -euo pipefail\nkubectl apply -f k8s/namespaces.yaml\n")
    _write_text(package_root / "docker-compose" / "docker-compose.yml", _compose_stub(manifest))
    _write_text(package_root / "docker-compose" / ".env.template", _env_template(manifest))
    _write_text(package_root / "scripts" / "check-prerequisites.sh", "#!/usr/bin/env bash\nset -euo pipefail\necho \"check prerequisites\"\n")
    _write_text(package_root / "security" / "image-digest-lock.json", json.dumps({"images": manifest["images"]}, ensure_ascii=False, indent=2) + "\n")

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


def _manifest(package_id: str, request: PackageBuildRequest, preview) -> dict:
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
