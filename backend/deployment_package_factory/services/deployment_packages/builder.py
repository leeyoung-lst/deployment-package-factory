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
DEFAULT_CONTAINER_PORT = 8080
MIDDLEWARE_PORTS = {
    "postgres": 5432,
    "dm": 5236,
    "redis": 6379,
    "minio": 9000,
    "qdrant": 6333,
    "camunda": 8080,
    "iotdb": 6667,
    "monitoring": 9090,
}


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
    _write_text(package_root / "docs" / "install-k8s.md", "# K8s 安装说明\n\n替换 `k8s/secrets.template.yaml` 后执行 `k8s/install.sh`。\n")
    _write_text(package_root / "docs" / "install-docker-compose.md", "# Docker Compose 安装说明\n\n根据 `.env.template` 创建 `.env` 后执行 `docker-compose/install.sh`。\n")
    _write_text(package_root / "k8s" / "namespaces.yaml", _k8s_namespaces(manifest))
    _write_text(package_root / "k8s" / "configmaps.yaml", _k8s_configmaps(manifest))
    _write_text(package_root / "k8s" / "secrets.template.yaml", _k8s_secrets(manifest))
    _write_text(package_root / "k8s" / "pvcs.yaml", _k8s_pvcs(manifest))
    _write_text(package_root / "k8s" / "deployments.yaml", _k8s_deployments(manifest))
    _write_text(package_root / "k8s" / "services.yaml", _k8s_services(manifest))
    _write_text(package_root / "k8s" / "ingress.yaml", _k8s_ingress(manifest))
    _write_text(package_root / "k8s" / "jobs" / "init-db.yaml", _k8s_init_job(manifest))
    _write_text(package_root / "k8s" / "install.sh", _k8s_install_script())
    _write_text(package_root / "k8s" / "uninstall.sh", _k8s_uninstall_script())
    _write_text(package_root / "docker-compose" / "docker-compose.yml", _compose_yaml(manifest))
    _write_text(package_root / "docker-compose" / ".env.template", _env_template(manifest))
    _write_text(package_root / "docker-compose" / "install.sh", _compose_install_script())
    _write_text(package_root / "docker-compose" / "uninstall.sh", _compose_uninstall_script())
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
        "databaseImage": preview.database.image,
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


def _k8s_configmaps(manifest: dict) -> str:
    docs = []
    for service in _service_specs(manifest):
        docs.append(
            "apiVersion: v1\n"
            "kind: ConfigMap\n"
            "metadata:\n"
            f"  name: {service['name']}-config\n"
            f"  namespace: {service['namespace']}\n"
            "data:\n"
            f"  APP_ENV: {manifest['targetEnv']}\n"
            f"  SERVICE_NAME: {service['name']}\n"
            f"  DATABASE_TYPE: {manifest['database']}\n"
        )
    return _join_yaml_docs(docs)


def _k8s_secrets(manifest: dict) -> str:
    namespaces = sorted({service["namespace"] for service in _service_specs(manifest)} | {_middleware_namespace(manifest)})
    docs = []
    for namespace in namespaces:
        docs.append(
            "apiVersion: v1\n"
            "kind: Secret\n"
            "metadata:\n"
            "  name: platform-runtime-secret\n"
            f"  namespace: {namespace}\n"
            "type: Opaque\n"
            "stringData:\n"
            "  DATABASE_PASSWORD: __REPLACE_WITH_DATABASE_PASSWORD__\n"
            "  REDIS_PASSWORD: __REPLACE_WITH_REDIS_PASSWORD__\n"
            "  MINIO_ROOT_PASSWORD: __REPLACE_WITH_MINIO_ROOT_PASSWORD__\n"
        )
    return _join_yaml_docs(docs)


def _k8s_pvcs(manifest: dict) -> str:
    docs = []
    for key in manifest["middleware"]:
        docs.append(
            "apiVersion: v1\n"
            "kind: PersistentVolumeClaim\n"
            "metadata:\n"
            f"  name: {key}-data\n"
            f"  namespace: {_middleware_namespace(manifest)}\n"
            "spec:\n"
            "  accessModes:\n"
            "    - ReadWriteOnce\n"
            "  resources:\n"
            "    requests:\n"
            "      storage: 20Gi\n"
            f"{_storage_class_block(manifest)}"
        )
    return _join_yaml_docs(docs)


def _k8s_deployments(manifest: dict) -> str:
    docs = [_k8s_app_deployment(service, manifest) for service in _service_specs(manifest)]
    docs.extend(_k8s_middleware_deployment(key, manifest) for key in manifest["middleware"])
    return _join_yaml_docs(docs)


def _k8s_app_deployment(service: dict, manifest: dict) -> str:
    replicas = 2 if service["group"] == "platform" else 1
    return (
        "apiVersion: apps/v1\n"
        "kind: Deployment\n"
        "metadata:\n"
        f"  name: {service['name']}\n"
        f"  namespace: {service['namespace']}\n"
        "spec:\n"
        f"  replicas: {replicas}\n"
        "  selector:\n"
        "    matchLabels:\n"
        f"      app: {service['name']}\n"
        "  template:\n"
        "    metadata:\n"
        "      labels:\n"
        f"        app: {service['name']}\n"
        "    spec:\n"
        "      containers:\n"
        f"        - name: {service['name']}\n"
        f"          image: {service['image']}\n"
        "          imagePullPolicy: IfNotPresent\n"
        "          ports:\n"
        f"            - containerPort: {service['port']}\n"
        "          envFrom:\n"
        "            - configMapRef:\n"
        f"                name: {service['name']}-config\n"
        "            - secretRef:\n"
        "                name: platform-runtime-secret\n"
    )


def _k8s_middleware_deployment(key: str, manifest: dict) -> str:
    port = MIDDLEWARE_PORTS.get(key, DEFAULT_CONTAINER_PORT)
    return (
        "apiVersion: apps/v1\n"
        "kind: Deployment\n"
        "metadata:\n"
        f"  name: {key}\n"
        f"  namespace: {_middleware_namespace(manifest)}\n"
        "spec:\n"
        "  replicas: 1\n"
        "  selector:\n"
        "    matchLabels:\n"
        f"      app: {key}\n"
        "  template:\n"
        "    metadata:\n"
        "      labels:\n"
        f"        app: {key}\n"
        "    spec:\n"
        "      containers:\n"
        f"        - name: {key}\n"
        f"          image: {_middleware_image(key, manifest)}\n"
        "          imagePullPolicy: IfNotPresent\n"
        "          ports:\n"
        f"            - containerPort: {port}\n"
        "          volumeMounts:\n"
        "            - name: data\n"
        f"              mountPath: /var/lib/{key}\n"
        "      volumes:\n"
        "        - name: data\n"
        "          persistentVolumeClaim:\n"
        f"            claimName: {key}-data\n"
    )


def _k8s_services(manifest: dict) -> str:
    docs = [_k8s_service(service["name"], service["namespace"], service["port"]) for service in _service_specs(manifest)]
    docs.extend(
        _k8s_service(key, _middleware_namespace(manifest), MIDDLEWARE_PORTS.get(key, DEFAULT_CONTAINER_PORT))
        for key in manifest["middleware"]
    )
    return _join_yaml_docs(docs)


def _k8s_service(name: str, namespace: str, port: int) -> str:
    return (
        "apiVersion: v1\n"
        "kind: Service\n"
        "metadata:\n"
        f"  name: {name}\n"
        f"  namespace: {namespace}\n"
        "spec:\n"
        "  type: ClusterIP\n"
        "  selector:\n"
        f"    app: {name}\n"
        "  ports:\n"
        "    - name: http\n"
        f"      port: {port}\n"
        f"      targetPort: {port}\n"
    )


def _k8s_ingress(manifest: dict) -> str:
    domain = manifest["targetProfile"].get("domain") or "prod.example.com"
    return (
        "apiVersion: networking.k8s.io/v1\n"
        "kind: Ingress\n"
        "metadata:\n"
        "  name: platform-gateway\n"
        f"  namespace: {_base_namespace(manifest)}\n"
        "spec:\n"
        "  rules:\n"
        f"    - host: {domain}\n"
        "      http:\n"
        "        paths:\n"
        "          - path: /\n"
        "            pathType: Prefix\n"
        "            backend:\n"
        "              service:\n"
        f"                name: {_frontend_service_name(manifest)}\n"
        "                port:\n"
        f"                  number: {DEFAULT_CONTAINER_PORT}\n"
    )


def _k8s_init_job(manifest: dict) -> str:
    return (
        "apiVersion: batch/v1\n"
        "kind: Job\n"
        "metadata:\n"
        "  name: init-database\n"
        f"  namespace: {_middleware_namespace(manifest)}\n"
        "spec:\n"
        "  template:\n"
        "    spec:\n"
        "      restartPolicy: OnFailure\n"
        "      containers:\n"
        "        - name: init-database\n"
        f"          image: {_middleware_image(manifest['database'], manifest)}\n"
        "          command: [\"/bin/sh\", \"-c\"]\n"
        f"          args: [\"echo init {manifest['database']} schema\"]\n"
    )


def _k8s_install_script() -> str:
    files = [
        "namespaces.yaml",
        "secrets.template.yaml",
        "configmaps.yaml",
        "pvcs.yaml",
        "deployments.yaml",
        "services.yaml",
        "ingress.yaml",
        "jobs/init-db.yaml",
    ]
    lines = ["#!/usr/bin/env bash", "set -euo pipefail", 'SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"']
    lines.extend(f'kubectl apply -f "${{SCRIPT_DIR}}/{item}"' for item in files)
    return "\n".join(lines) + "\n"


def _k8s_uninstall_script() -> str:
    return (
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        'SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"\n'
        'kubectl delete -f "${SCRIPT_DIR}" --recursive --ignore-not-found=true\n'
    )


def _compose_yaml(manifest: dict) -> str:
    services: list[str] = []
    services.extend(_compose_middleware_service(key, manifest) for key in manifest["middleware"])
    services.extend(_compose_app_service(service, manifest) for service in _service_specs(manifest))
    return (
        "services:\n"
        + "\n".join(services)
        + "\nnetworks:\n"
        "  base-public:\n"
        "  middleware:\n"
        + "".join(f"  business-{item}:\n" for item in manifest["businessServices"])
        + "volumes:\n"
        + "".join(f"  {key}-data:\n" for key in manifest["middleware"])
    )


def _compose_middleware_service(key: str, manifest: dict) -> str:
    port = MIDDLEWARE_PORTS.get(key, DEFAULT_CONTAINER_PORT)
    return (
        f"  {key}:\n"
        f"    image: {_middleware_image(key, manifest)}\n"
        "    restart: unless-stopped\n"
        "    networks:\n"
        "      - middleware\n"
        "    ports:\n"
        f"      - \"{port}:{port}\"\n"
        "    volumes:\n"
        f"      - {key}-data:/var/lib/{key}\n"
    )


def _compose_app_service(service: dict, manifest: dict) -> str:
    networks = ["base-public", "middleware"]
    if service["group"] == "business":
        networks.append(service["namespace"].split("business-", 1)[-1])
    return (
        f"  {service['name']}:\n"
        f"    image: {service['image']}\n"
        "    restart: unless-stopped\n"
        "    env_file:\n"
        "      - .env\n"
        "    environment:\n"
        f"      SERVICE_NAME: {service['name']}\n"
        f"      DATABASE_TYPE: {manifest['database']}\n"
        "    networks:\n"
        + "".join(f"      - {network}\n" for network in networks)
        + "    depends_on:\n"
        + "".join(f"      - {key}\n" for key in manifest["middleware"])
        + "    ports:\n"
        f"      - \"{service['hostPort']}:{service['port']}\"\n"
    )


def _compose_install_script() -> str:
    return "#!/usr/bin/env bash\nset -euo pipefail\ndocker compose --env-file .env -f docker-compose.yml up -d\n"


def _compose_uninstall_script() -> str:
    return "#!/usr/bin/env bash\nset -euo pipefail\ndocker compose --env-file .env -f docker-compose.yml down\n"


def _env_template(manifest: dict) -> str:
    registry = manifest["targetProfile"].get("registry") or "harbor.example.com/local-ai"
    return (
        f"REGISTRY={registry}\n"
        "IMAGE_TAG=prod\n"
        "FRONTEND_PORT=80\n"
        "DATABASE_PASSWORD=__REPLACE_WITH_DATABASE_PASSWORD__\n"
        "REDIS_PASSWORD=__REPLACE_WITH_REDIS_PASSWORD__\n"
        "MINIO_ROOT_PASSWORD=__REPLACE_WITH_MINIO_ROOT_PASSWORD__\n"
    )


def _join_yaml_docs(docs: list[str]) -> str:
    return "---\n".join(item.rstrip() + "\n" for item in docs if item.strip())


def _service_specs(manifest: dict) -> list[dict]:
    specs: list[dict] = []
    counters = {"platform": 0, "business": 0}
    for group in ("platform", "business"):
        for image in manifest["images"].get(group, []):
            source_ref = _with_default_tag(image)
            entry = _image_entry_for_source(manifest, source_ref)
            name = _service_name_from_image(image)
            namespace = _base_namespace(manifest) if group == "platform" else _business_namespace(manifest, name)
            counters[group] += 1
            specs.append(
                {
                    "name": name,
                    "group": group,
                    "image": entry["targetRef"],
                    "namespace": namespace,
                    "port": 80 if "frontend" in name or name.startswith("sub-app") else DEFAULT_CONTAINER_PORT,
                    "hostPort": 18080 + (0 if group == "platform" else 100) + counters[group],
                }
            )
    return specs


def _image_entry_for_source(manifest: dict, source_ref: str) -> dict:
    for item in manifest["imageEntries"]:
        if item["sourceRef"] == source_ref:
            return item
    raise PackageBuildError(f"Image entry not found for {source_ref}.")


def _middleware_image(key: str, manifest: dict) -> str:
    source_ref = _with_default_tag(manifest["databaseImage"]) if key == manifest["database"] else _middleware_source_ref(key, manifest)
    for item in manifest["imageEntries"]:
        if item["sourceRef"] == source_ref:
            return item["targetRef"]
    return _target_image_ref(source_ref, manifest["targetProfile"].get("registry", ""))


def _middleware_source_ref(key: str, manifest: dict) -> str:
    for item in manifest["imageEntries"]:
        if item["group"] == "middleware" and item["sourceRef"].startswith(f"{key}:"):
            return item["sourceRef"]
    for item in manifest["imageEntries"]:
        if item["group"] == "middleware" and key in item["sourceRef"]:
            return item["sourceRef"]
    raise PackageBuildError(f"Middleware image entry not found for {key}.")


def _service_name_from_image(image: str) -> str:
    name = image.rsplit("/", 1)[-1].split(":", 1)[0].split("@", 1)[0]
    return _safe_resource_name(name)


def _safe_resource_name(value: str) -> str:
    value = re.sub(r"[^a-z0-9-]+", "-", value.lower()).strip("-")
    return value or "service"


def _base_namespace(manifest: dict) -> str:
    prefix = manifest["targetProfile"].get("namespacePrefix") or "prod"
    return f"{prefix}-base-public"


def _middleware_namespace(manifest: dict) -> str:
    prefix = manifest["targetProfile"].get("namespacePrefix") or "prod"
    return f"{prefix}-middleware"


def _business_namespace(manifest: dict, service_name: str) -> str:
    prefix = manifest["targetProfile"].get("namespacePrefix") or "prod"
    for business in manifest["businessServices"]:
        if business in service_name:
            return f"{prefix}-business-{business}"
    fallback = manifest["businessServices"][0] if manifest["businessServices"] else "default"
    return f"{prefix}-business-{fallback}"


def _frontend_service_name(manifest: dict) -> str:
    services = _service_specs(manifest)
    for service in services:
        if "frontend" in service["name"]:
            return service["name"]
    return services[0]["name"] if services else "frontend"


def _storage_class_block(manifest: dict) -> str:
    storage_class = manifest["targetProfile"].get("storageClass")
    if not storage_class:
        return ""
    return f"  storageClassName: {storage_class}\n"


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
