from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import PurePosixPath


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


@dataclass(frozen=True)
class RenderedDeploymentFile:
    path: PurePosixPath
    content: str
    executable: bool = False


def render_deployment_files(manifest: dict) -> list[RenderedDeploymentFile]:
    return [
        RenderedDeploymentFile(PurePosixPath("k8s/namespaces.yaml"), _k8s_namespaces(manifest)),
        RenderedDeploymentFile(PurePosixPath("k8s/configmaps.yaml"), _k8s_configmaps(manifest)),
        RenderedDeploymentFile(PurePosixPath("k8s/secrets.template.yaml"), _k8s_secrets(manifest)),
        RenderedDeploymentFile(PurePosixPath("k8s/pvcs.yaml"), _k8s_pvcs(manifest)),
        RenderedDeploymentFile(PurePosixPath("k8s/deployments.yaml"), _k8s_deployments(manifest)),
        RenderedDeploymentFile(PurePosixPath("k8s/services.yaml"), _k8s_services(manifest)),
        RenderedDeploymentFile(PurePosixPath("k8s/ingress.yaml"), _k8s_ingress(manifest)),
        RenderedDeploymentFile(PurePosixPath("k8s/jobs/init-db.yaml"), _k8s_init_job(manifest)),
        RenderedDeploymentFile(PurePosixPath("k8s/install.sh"), _k8s_install_script(), executable=True),
        RenderedDeploymentFile(PurePosixPath("k8s/uninstall.sh"), _k8s_uninstall_script(), executable=True),
        RenderedDeploymentFile(PurePosixPath("k8s/dry-run.sh"), _k8s_dry_run_script(), executable=True),
        RenderedDeploymentFile(PurePosixPath("docker-compose/docker-compose.yml"), _compose_yaml(manifest)),
        RenderedDeploymentFile(PurePosixPath("docker-compose/.env.template"), _env_template(manifest)),
        RenderedDeploymentFile(PurePosixPath("docker-compose/install.sh"), _compose_install_script(), executable=True),
        RenderedDeploymentFile(PurePosixPath("docker-compose/uninstall.sh"), _compose_uninstall_script(), executable=True),
        RenderedDeploymentFile(PurePosixPath("docker-compose/dry-run.sh"), _compose_dry_run_script(), executable=True),
        RenderedDeploymentFile(PurePosixPath("scripts/check-prerequisites.sh"), _check_prerequisites_script(), executable=True),
        RenderedDeploymentFile(PurePosixPath("scripts/secret-check.sh"), _secret_check_script(), executable=True),
        RenderedDeploymentFile(PurePosixPath("scripts/health-check.sh"), _health_check_script(manifest), executable=True),
    ]


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
    docs = [_k8s_app_deployment(service) for service in _service_specs(manifest)]
    docs.extend(_k8s_middleware_deployment(key, manifest) for key in manifest["middleware"])
    return _join_yaml_docs(docs)


def _k8s_app_deployment(service: dict) -> str:
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
        "configmaps.yaml",
        "pvcs.yaml",
        "deployments.yaml",
        "services.yaml",
        "ingress.yaml",
        "jobs/init-db.yaml",
    ]
    lines = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        'SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"',
        'PACKAGE_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"',
        '"${PACKAGE_ROOT}/scripts/check-prerequisites.sh" k8s',
        '"${PACKAGE_ROOT}/scripts/secret-check.sh" k8s',
        'SECRETS_FILE="${SCRIPT_DIR}/secrets.yaml"',
        'if [ ! -f "${SECRETS_FILE}" ]; then',
        '  SECRETS_FILE="${SCRIPT_DIR}/secrets.template.yaml"',
        "fi",
        'kubectl apply -f "${SCRIPT_DIR}/namespaces.yaml"',
    ]
    lines.append('kubectl apply -f "${SECRETS_FILE}"')
    lines.extend(f'kubectl apply -f "${{SCRIPT_DIR}}/{item}"' for item in files)
    return "\n".join(lines) + "\n"


def _k8s_dry_run_script() -> str:
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
    lines = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        'SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"',
        'PACKAGE_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"',
        '"${PACKAGE_ROOT}/scripts/check-prerequisites.sh" k8s',
    ]
    lines.extend(f'kubectl apply --dry-run=client -f "${{SCRIPT_DIR}}/{item}"' for item in files)
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
    return (
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        'SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"\n'
        'PACKAGE_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"\n'
        '"${PACKAGE_ROOT}/scripts/check-prerequisites.sh" docker-compose\n'
        '"${PACKAGE_ROOT}/scripts/secret-check.sh" docker-compose\n'
        'docker compose --env-file "${SCRIPT_DIR}/.env" -f "${SCRIPT_DIR}/docker-compose.yml" up -d\n'
    )


def _compose_uninstall_script() -> str:
    return (
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        'SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"\n'
        'ENV_FILE="${SCRIPT_DIR}/.env"\n'
        'if [ ! -f "${ENV_FILE}" ]; then\n'
        '  ENV_FILE="${SCRIPT_DIR}/.env.template"\n'
        "fi\n"
        'docker compose --env-file "${ENV_FILE}" -f "${SCRIPT_DIR}/docker-compose.yml" down\n'
    )


def _compose_dry_run_script() -> str:
    return (
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        'SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"\n'
        'PACKAGE_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"\n'
        'ENV_FILE="${SCRIPT_DIR}/.env"\n'
        'if [ ! -f "${ENV_FILE}" ]; then\n'
        '  ENV_FILE="${SCRIPT_DIR}/.env.template"\n'
        "fi\n"
        '"${PACKAGE_ROOT}/scripts/check-prerequisites.sh" docker-compose\n'
        'docker compose --env-file "${ENV_FILE}" -f "${SCRIPT_DIR}/docker-compose.yml" config\n'
    )


def _check_prerequisites_script() -> str:
    return (
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        'MODE="${1:-all}"\n'
        "\n"
        "require_command() {\n"
        '  if ! command -v "$1" >/dev/null 2>&1; then\n'
        '    echo "Missing required command: $1" >&2\n'
        "    exit 1\n"
        "  fi\n"
        "}\n"
        "\n"
        'case "${MODE}" in\n'
        "  all)\n"
        "    require_command docker\n"
        "    require_command kubectl\n"
        "    ;;\n"
        "  k8s)\n"
        "    require_command kubectl\n"
        "    ;;\n"
        "  docker-compose)\n"
        "    require_command docker\n"
        "    docker compose version >/dev/null\n"
        "    ;;\n"
        "  *)\n"
        '    echo "Unknown prerequisite mode: ${MODE}" >&2\n'
        "    exit 1\n"
        "    ;;\n"
        "esac\n"
        "\n"
        'echo "Prerequisite check passed for ${MODE}."\n'
    )


def _secret_check_script() -> str:
    return (
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        'MODE="${1:-all}"\n'
        'SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"\n'
        'PACKAGE_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"\n'
        "\n"
        "files=()\n"
        'if [ "${MODE}" = "all" ] || [ "${MODE}" = "k8s" ]; then\n'
        '  if [ -f "${PACKAGE_ROOT}/k8s/secrets.yaml" ]; then\n'
        '    files+=("${PACKAGE_ROOT}/k8s/secrets.yaml")\n'
        '  elif [ -f "${PACKAGE_ROOT}/k8s/secrets.template.yaml" ]; then\n'
        '    files+=("${PACKAGE_ROOT}/k8s/secrets.template.yaml")\n'
        "  fi\n"
        "fi\n"
        "\n"
        'if [ "${MODE}" = "all" ] || [ "${MODE}" = "docker-compose" ]; then\n'
        '  if [ -f "${PACKAGE_ROOT}/docker-compose/.env" ]; then\n'
        '    files+=("${PACKAGE_ROOT}/docker-compose/.env")\n'
        '  elif [ -f "${PACKAGE_ROOT}/docker-compose/.env.template" ]; then\n'
        '    files+=("${PACKAGE_ROOT}/docker-compose/.env.template")\n'
        "  fi\n"
        "fi\n"
        "\n"
        'if [ "${MODE}" != "all" ] && [ "${MODE}" != "k8s" ] && [ "${MODE}" != "docker-compose" ]; then\n'
        '  echo "Unknown secret check mode: ${MODE}" >&2\n'
        "  exit 1\n"
        "fi\n"
        "\n"
        'if [ "${#files[@]}" -eq 0 ]; then\n'
        '  echo "No secret files found to validate." >&2\n'
        "  exit 1\n"
        "fi\n"
        "\n"
        'if grep -H "__REPLACE_WITH_" "${files[@]}" >/tmp/deployment-package-secret-placeholders.txt; then\n'
        '  echo "Secret placeholders remain. Replace them before installation:" >&2\n'
        "  cat /tmp/deployment-package-secret-placeholders.txt >&2\n"
        "  exit 1\n"
        "fi\n"
        "\n"
        'echo "Secret placeholder check passed."\n'
    )


def _health_check_script(manifest: dict) -> str:
    namespaces = sorted({_base_namespace(manifest), _middleware_namespace(manifest)} | {_business_namespace(manifest, item) for item in manifest["businessServices"]})
    namespace_args = " ".join(namespaces)
    return (
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        'MODE="${1:-k8s}"\n'
        f'NAMESPACES="{namespace_args}"\n'
        "\n"
        'case "${MODE}" in\n'
        "  k8s)\n"
        "    if ! command -v kubectl >/dev/null 2>&1; then\n"
        '      echo "kubectl is required for k8s health checks." >&2\n'
        "      exit 1\n"
        "    fi\n"
        "    for namespace in ${NAMESPACES}; do\n"
        '      echo "Checking namespace ${namespace}"\n'
        '      kubectl get pods -n "${namespace}"\n'
        "    done\n"
        "    ;;\n"
        "  docker-compose)\n"
        "    if ! command -v docker >/dev/null 2>&1; then\n"
        '      echo "docker is required for docker-compose health checks." >&2\n'
        "      exit 1\n"
        "    fi\n"
        '    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"\n'
        '    PACKAGE_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"\n'
        '    docker compose --env-file "${PACKAGE_ROOT}/docker-compose/.env" -f "${PACKAGE_ROOT}/docker-compose/docker-compose.yml" ps\n'
        "    ;;\n"
        "  *)\n"
        '    echo "Unknown health check mode: ${MODE}" >&2\n'
        "    exit 1\n"
        "    ;;\n"
        "esac\n"
    )


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
    raise ValueError(f"Image entry not found for {source_ref}.")


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
    raise ValueError(f"Middleware image entry not found for {key}.")


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


def _with_default_tag(image: str) -> str:
    image = image.strip()
    if not image:
        raise ValueError("Image reference cannot be empty.")
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
