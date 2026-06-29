from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import PurePosixPath


DEFAULT_CONTAINER_PORT = 8080
K8S_LAYERS: tuple[tuple[str, str], ...] = (
    ("00-platform", "Platform bootstrap: namespaces, shared config, and externally managed secrets"),
    ("10-data", "Data services: database, Redis, MinIO, Qdrant, and other data middleware"),
    ("20-observability", "Observability services: Prometheus, Alertmanager, Grafana, and telemetry helpers"),
    ("30-edge", "Edge services: IoTDB, MQTT broker, collectors, and collection metrics"),
    ("40-workflow-webui", "Workflow and AI web UI services: Camunda, Elasticsearch, and Open WebUI"),
    ("50-simulators", "Simulation services: HA collectors and machine tool simulators"),
    ("60-apps", "Application services: backend, IAM, business services, frontend, ingress, and init jobs"),
)


@dataclass(frozen=True)
class RenderedDeploymentFile:
    path: PurePosixPath
    content: str
    executable: bool = False


def render_deployment_files(manifest: dict) -> list[RenderedDeploymentFile]:
    layer_resources = _k8s_layer_resource_map(manifest)
    files = [
        RenderedDeploymentFile(PurePosixPath("k8s/namespaces.yaml"), _k8s_namespaces(manifest)),
        RenderedDeploymentFile(PurePosixPath("k8s/configmaps.yaml"), _k8s_configmaps(manifest)),
        RenderedDeploymentFile(PurePosixPath("k8s/secrets.template.yaml"), _k8s_secrets(manifest)),
        RenderedDeploymentFile(PurePosixPath("k8s/pvcs.yaml"), _k8s_pvcs(manifest)),
        RenderedDeploymentFile(PurePosixPath("k8s/deployments.yaml"), _k8s_deployments(manifest)),
        RenderedDeploymentFile(PurePosixPath("k8s/services.yaml"), _k8s_services(manifest)),
        RenderedDeploymentFile(PurePosixPath("k8s/ingress.yaml"), _k8s_ingress(manifest)),
        RenderedDeploymentFile(PurePosixPath("k8s/jobs/init-db.yaml"), _k8s_init_job(manifest)),
        RenderedDeploymentFile(PurePosixPath("k8s/kustomization.yaml"), _k8s_root_kustomization(layer_resources)),
        RenderedDeploymentFile(PurePosixPath("k8s/layers/README.md"), _k8s_layers_readme()),
        RenderedDeploymentFile(PurePosixPath("k8s/install.sh"), _k8s_install_script(layer_resources), executable=True),
        RenderedDeploymentFile(PurePosixPath("k8s/uninstall.sh"), _k8s_uninstall_script(), executable=True),
        RenderedDeploymentFile(PurePosixPath("k8s/dry-run.sh"), _k8s_dry_run_script(layer_resources), executable=True),
        RenderedDeploymentFile(PurePosixPath("docker-compose/docker-compose.yml"), _compose_yaml(manifest)),
        RenderedDeploymentFile(PurePosixPath("docker-compose/.env"), _env_defaults(manifest)),
        RenderedDeploymentFile(PurePosixPath("docker-compose/.env.template"), _env_template(manifest)),
        RenderedDeploymentFile(PurePosixPath("docker-compose/install.sh"), _compose_install_script(), executable=True),
        RenderedDeploymentFile(PurePosixPath("docker-compose/uninstall.sh"), _compose_uninstall_script(), executable=True),
        RenderedDeploymentFile(PurePosixPath("docker-compose/dry-run.sh"), _compose_dry_run_script(), executable=True),
        RenderedDeploymentFile(PurePosixPath("scripts/check-prerequisites.sh"), _check_prerequisites_script(), executable=True),
        RenderedDeploymentFile(PurePosixPath("scripts/secret-check.sh"), _secret_check_script(), executable=True),
        RenderedDeploymentFile(PurePosixPath("scripts/health-check.sh"), _health_check_script(manifest), executable=True),
    ]
    files.extend(_k8s_layer_files(layer_resources))
    return files


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
    string_data = _secret_string_data(manifest)
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
            f"{string_data}"
        )
    return _join_yaml_docs(docs)


def _k8s_pvcs(manifest: dict) -> str:
    docs = []
    for key in _runtime_middleware_keys(manifest):
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
    docs.extend(_k8s_middleware_deployment(key, manifest) for key in _runtime_middleware_keys(manifest))
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
    port = _middleware_port(key, manifest)
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
        f"              mountPath: {_middleware_data_path(key, manifest)}\n"
        "      volumes:\n"
        "        - name: data\n"
        "          persistentVolumeClaim:\n"
        f"            claimName: {key}-data\n"
    )


def _k8s_services(manifest: dict) -> str:
    docs = [_k8s_service(service["name"], service["namespace"], service["port"]) for service in _service_specs(manifest)]
    docs.extend(
        _k8s_service(key, _middleware_namespace(manifest), _middleware_port(key, manifest))
        for key in _runtime_middleware_keys(manifest)
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
        "apiVersion: v1\n"
        "kind: ConfigMap\n"
        "metadata:\n"
        "  name: init-scripts\n"
        f"  namespace: {_middleware_namespace(manifest)}\n"
        "data:\n"
        "  run-init.sh: |\n"
        "    #!/usr/bin/env bash\n"
        "    set -euo pipefail\n"
        f"    echo init {manifest['database']} schema and middleware scripts\n"
        "---\n"
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
        "          command: [\"/bin/sh\", \"/init/run-init.sh\"]\n"
        "          volumeMounts:\n"
        "            - name: init-scripts\n"
        "              mountPath: /init\n"
        "      volumes:\n"
        "        - name: init-scripts\n"
        "          configMap:\n"
        "            name: init-scripts\n"
        "            defaultMode: 0755\n"
    )


def _k8s_layer_files(layer_resources: dict[str, list[tuple[str, str]]]) -> list[RenderedDeploymentFile]:
    files: list[RenderedDeploymentFile] = []
    for layer, description in K8S_LAYERS:
        resources = layer_resources.get(layer, [])
        files.append(RenderedDeploymentFile(PurePosixPath(f"k8s/layers/{layer}/README.md"), _k8s_layer_readme(layer, description, resources)))
        files.append(RenderedDeploymentFile(PurePosixPath(f"k8s/layers/{layer}/kustomization.yaml"), _k8s_layer_kustomization(layer, resources)))
        for filename, content in resources:
            files.append(RenderedDeploymentFile(PurePosixPath(f"k8s/layers/{layer}/{filename}"), content))
    return files


def _k8s_layer_resource_map(manifest: dict) -> dict[str, list[tuple[str, str]]]:
    platform_resources = [
        ("namespaces.yaml", _k8s_namespaces(manifest)),
        ("configmaps.yaml", _k8s_configmaps(manifest)),
        ("secrets.template.yaml", _k8s_secrets(manifest)),
    ]
    data_keys = [key for key in _runtime_middleware_keys(manifest) if _k8s_layer_for_middleware(key) == "10-data"]
    edge_keys = [key for key in _runtime_middleware_keys(manifest) if _k8s_layer_for_middleware(key) == "30-edge"]
    workflow_keys = [key for key in _runtime_middleware_keys(manifest) if _k8s_layer_for_middleware(key) == "40-workflow-webui"]
    apps = _service_specs(manifest)
    return {
        "00-platform": platform_resources,
        "10-data": _k8s_middleware_resources(data_keys, manifest),
        "20-observability": _k8s_observability_resources(manifest),
        "30-edge": _k8s_middleware_resources(edge_keys, manifest),
        "40-workflow-webui": _k8s_middleware_resources(workflow_keys, manifest),
        "50-simulators": [],
        "60-apps": [
            ("deployments.yaml", _join_yaml_docs(_k8s_app_deployment(service) for service in apps)),
            ("services.yaml", _join_yaml_docs(_k8s_service(service["name"], service["namespace"], service["port"]) for service in apps)),
            ("ingress.yaml", _k8s_ingress(manifest)),
            ("jobs-init-db.yaml", _k8s_init_job(manifest)),
        ],
    }


def _k8s_layer_for_middleware(key: str) -> str:
    if key in {"iotdb", "mqtt", "mqtt-broker", "mqtt-collector", "collection-metrics"}:
        return "30-edge"
    if key in {"camunda", "camunda-elasticsearch", "open-webui"}:
        return "40-workflow-webui"
    if key in {"monitoring", "prometheus", "grafana", "alertmanager"}:
        return "20-observability"
    return "10-data"


def _k8s_middleware_resources(keys: list[str], manifest: dict) -> list[tuple[str, str]]:
    if not keys:
        return []
    return [
        ("pvcs.yaml", _k8s_pvcs_for_keys(keys, manifest)),
        ("deployments.yaml", _join_yaml_docs(_k8s_middleware_deployment(key, manifest) for key in keys)),
        ("services.yaml", _join_yaml_docs(_k8s_service(key, _middleware_namespace(manifest), _middleware_port(key, manifest)) for key in keys)),
    ]


def _k8s_observability_resources(manifest: dict) -> list[tuple[str, str]]:
    if "monitoring" not in _runtime_middleware_keys(manifest):
        return []
    return _k8s_middleware_resources(["monitoring"], manifest)


def _k8s_pvcs_for_keys(keys: list[str], manifest: dict) -> str:
    docs = []
    for key in keys:
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


def _k8s_root_kustomization(layer_resources: dict[str, list[tuple[str, str]]]) -> str:
    resources = [
        f"  - layers/{layer}"
        for layer, _description in K8S_LAYERS
        if layer_resources.get(layer)
    ]
    return "apiVersion: kustomize.config.k8s.io/v1beta1\nkind: Kustomization\nresources:\n" + "\n".join(resources) + "\n"


def _k8s_layer_kustomization(layer: str, resources: list[tuple[str, str]]) -> str:
    if not resources:
        return (
            "apiVersion: kustomize.config.k8s.io/v1beta1\n"
            "kind: Kustomization\n"
            "resources: []\n"
            f"# {layer} has no selected resources in this package.\n"
        )
    lines = [
        "apiVersion: kustomize.config.k8s.io/v1beta1",
        "kind: Kustomization",
        "resources:",
    ]
    lines.extend(f"  - {filename}" for filename, _content in resources)
    return "\n".join(lines) + "\n"


def _k8s_layers_readme() -> str:
    lines = [
        "# K8s Layers",
        "",
        "The package mirrors the source K8s stack layering used by the local-ai environment.",
        "Apply layers in order; empty layers are retained as extension points for future middleware.",
        "",
    ]
    lines.extend(f"- `{layer}`: {description}" for layer, description in K8S_LAYERS)
    return "\n".join(lines) + "\n"


def _k8s_layer_readme(layer: str, description: str, resources: list[tuple[str, str]]) -> str:
    lines = [
        f"# {layer}",
        "",
        description,
        "",
        "Resources:",
    ]
    if resources:
        lines.extend(f"- `{filename}`" for filename, _content in resources)
    else:
        lines.append("- None selected for this package.")
    return "\n".join(lines) + "\n"


def _k8s_apply_layer_commands(layer_resources: dict[str, list[tuple[str, str]]], prefix: str = "") -> list[str]:
    return [
        f'{prefix}kubectl apply -k "${{SCRIPT_DIR}}/layers/{layer}"'
        for layer, _description in K8S_LAYERS
        if layer_resources.get(layer)
    ]


def _k8s_dry_run_layer_commands(layer_resources: dict[str, list[tuple[str, str]]], prefix: str = "") -> list[str]:
    return [
        f'{prefix}kubectl apply --dry-run=client -k "${{SCRIPT_DIR}}/layers/{layer}"'
        for layer, _description in K8S_LAYERS
        if layer_resources.get(layer)
    ]


def _k8s_install_script(layer_resources: dict[str, list[tuple[str, str]]]) -> str:
    lines = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        'SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"',
        'PACKAGE_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"',
        '"${PACKAGE_ROOT}/scripts/check-prerequisites.sh" k8s',
        '"${PACKAGE_ROOT}/scripts/secret-check.sh" k8s',
        'if [ -f "${SCRIPT_DIR}/secrets.yaml" ]; then',
        '  cp "${SCRIPT_DIR}/secrets.yaml" "${SCRIPT_DIR}/layers/00-platform/secrets.template.yaml"',
        "fi",
    ]
    lines.extend(_k8s_apply_layer_commands(layer_resources))
    return "\n".join(lines) + "\n"


def _k8s_dry_run_script(layer_resources: dict[str, list[tuple[str, str]]]) -> str:
    lines = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        'SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"',
        'PACKAGE_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"',
        '"${PACKAGE_ROOT}/scripts/check-prerequisites.sh" k8s',
    ]
    lines.extend(_k8s_dry_run_layer_commands(layer_resources))
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
    services.extend(_compose_middleware_service(key, manifest) for key in _runtime_middleware_keys(manifest))
    services.extend(_compose_app_service(service, manifest) for service in _service_specs(manifest))
    return (
        "services:\n"
        + "\n".join(services)
        + "\nnetworks:\n"
        "  base-public:\n"
        "  middleware:\n"
        + "".join(f"  business-{item}:\n" for item in manifest["businessServices"])
        + "volumes:\n"
        + "".join(f"  {key}-data:\n" for key in _runtime_middleware_keys(manifest))
    )


def _compose_middleware_service(key: str, manifest: dict) -> str:
    port = _middleware_port(key, manifest)
    environment = _compose_middleware_environment(key, manifest)
    command = _compose_middleware_command(key, manifest)
    healthcheck = _compose_middleware_healthcheck(key, manifest)
    return (
        f"  {key}:\n"
        f"    image: {_middleware_image(key, manifest)}\n"
        "    restart: unless-stopped\n"
        "    env_file:\n"
        "      - .env\n"
        f"{environment}"
        f"{command}"
        "    networks:\n"
        "      - middleware\n"
        "    ports:\n"
        f"      - \"{port}:{port}\"\n"
        "    volumes:\n"
        f"      - {key}-data:{_middleware_data_path(key, manifest)}\n"
        f"{healthcheck}"
    )


def _compose_middleware_environment(key: str, manifest: dict) -> str:
    values = _middleware_definition(key, manifest).get("composeEnvironment") or {}
    if not values:
        return ""
    lines = ["    environment:"]
    lines.extend(f"      {name}: {value}" for name, value in values.items())
    return "\n".join(lines) + "\n"


def _compose_middleware_command(key: str, manifest: dict) -> str:
    command = _middleware_definition(key, manifest).get("composeCommand") or []
    if not command:
        return ""
    values = ", ".join(f'"{_escape_compose_command_arg(item)}"' for item in command)
    return f"    command: [{values}]\n"


def _compose_middleware_healthcheck(key: str, manifest: dict) -> str:
    healthcheck = _middleware_definition(key, manifest).get("composeHealthcheck") or {}
    if not healthcheck:
        return ""
    lines = ["    healthcheck:"]
    test = healthcheck.get("test") or []
    if test:
        test_values = ", ".join(f'"{_escape_compose_command_arg(item)}"' for item in test)
        lines.append(f"      test: [{test_values}]")
    fields = {
        "interval": "interval",
        "timeout": "timeout",
        "retries": "retries",
        "startPeriod": "start_period",
    }
    for source, target in fields.items():
        value = healthcheck.get(source)
        if value is None or value == "":
            continue
        lines.append(f"      {target}: {value}")
    return "\n".join(lines) + "\n"


def _escape_compose_command_arg(value: str) -> str:
    return str(value).replace("\\", "\\\\").replace('"', '\\"')


def _compose_app_service(service: dict, manifest: dict) -> str:
    networks = ["base-public", "middleware"]
    if service["group"] == "business":
        networks.append(f"business-{service.get('businessKey') or service['namespace'].split('business-', 1)[-1]}")
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
        + "".join(f"      {key}:\n        condition: service_healthy\n" for key in _runtime_middleware_keys(manifest))
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
        '"${PACKAGE_ROOT}/init/run-init.sh" all\n'
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
        'SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"\n'
        'PACKAGE_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"\n'
        "\n"
        "require_command() {\n"
        '  if ! command -v "$1" >/dev/null 2>&1; then\n'
        '    echo "Missing required command: $1" >&2\n'
        "    exit 1\n"
        "  fi\n"
        "}\n"
        "\n"
        "package_bytes() {\n"
        '  if command -v python3 >/dev/null 2>&1 && [ -f "${PACKAGE_ROOT}/deploy-values.json" ]; then\n'
        '    python3 - "${PACKAGE_ROOT}/deploy-values.json" <<\'PY\'\n'
        "import json\n"
        "import sys\n"
        "from pathlib import Path\n"
        "values = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))\n"
        "print(int(values.get('validationSummary', {}).get('packageIndexTotalBytes') or 0))\n"
        "PY\n"
        "    return 0\n"
        "  fi\n"
        '  if command -v python3 >/dev/null 2>&1 && [ -f "${PACKAGE_ROOT}/package-index.json" ]; then\n'
        '    python3 - "${PACKAGE_ROOT}/package-index.json" <<\'PY\'\n'
        "import json\n"
        "import sys\n"
        "from pathlib import Path\n"
        "index = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))\n"
        "print(int(index.get('summary', {}).get('totalBytes') or 0))\n"
        "PY\n"
        "    return 0\n"
        "  fi\n"
        "  echo 0\n"
        "}\n"
        "\n"
        "check_disk_space() {\n"
        '  local required_bytes="$(package_bytes)"\n'
        '  if [ "${required_bytes}" -le 0 ]; then\n'
        '    echo "Disk space check skipped: package size metadata unavailable."\n'
        "    return 0\n"
        "  fi\n"
        '  local available_kb="$(df -Pk "${PACKAGE_ROOT}" | awk \'NR==2 {print $4}\')"\n'
        '  local available_bytes=$((available_kb * 1024))\n'
        '  local minimum_bytes=$((required_bytes * 2))\n'
        '  if [ "${available_bytes}" -lt "${minimum_bytes}" ]; then\n'
        '    echo "Insufficient disk space: need at least ${minimum_bytes} bytes, available ${available_bytes} bytes." >&2\n'
        "    exit 1\n"
        "  fi\n"
        '  echo "Disk space check passed: available ${available_bytes} bytes."\n'
        "}\n"
        "\n"
        "check_image_archives() {\n"
        '  if [ ! -f "${PACKAGE_ROOT}/deploy-values.json" ]; then\n'
        '    echo "deploy-values.json not found; image archive preflight skipped."\n'
        "    return 0\n"
        "  fi\n"
        '  if ! command -v python3 >/dev/null 2>&1; then\n'
        '    echo "python3 is not available; image archive preflight skipped."\n'
        "    return 0\n"
        "  fi\n"
        '  python3 - "${PACKAGE_ROOT}" <<\'PY\'\n'
        "import json\n"
        "import sys\n"
        "from pathlib import Path\n"
        "root = Path(sys.argv[1])\n"
        "values = json.loads((root / 'deploy-values.json').read_text(encoding='utf-8'))\n"
        "if values.get('imageMode') != 'image-archive':\n"
        "    raise SystemExit(0)\n"
        "missing = []\n"
        "for image in values.get('images', []):\n"
        "    archive = image.get('archiveFile') or ''\n"
        "    if archive and not (root / 'images' / 'archives' / archive).is_file():\n"
        "        missing.append(archive)\n"
        "if missing:\n"
        "    print('Missing image archives: ' + ', '.join(missing), file=sys.stderr)\n"
        "    raise SystemExit(1)\n"
        "print('Image archive preflight passed.')\n"
        "PY\n"
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
        "check_disk_space\n"
        "check_image_archives\n"
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
        '    COMPOSE_FILE="${PACKAGE_ROOT}/docker-compose/docker-compose.yml"\n'
        '    ENV_FILE="${PACKAGE_ROOT}/docker-compose/.env"\n'
        '    if ! output="$(docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" ps --format json 2>/dev/null)"; then\n'
        '      docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" ps\n'
        '      echo "Strict docker-compose health check skipped: this Docker Compose version does not support ps --format json." >&2\n'
        "      exit 0\n"
        "    fi\n"
        '    if [ -z "${output}" ]; then\n'
        '      echo "No docker-compose services are running." >&2\n'
        "      exit 1\n"
        "    fi\n"
        '    if ! command -v python3 >/dev/null 2>&1; then\n'
        '      echo "python3 is not available; strict docker-compose health check skipped." >&2\n'
        "      exit 0\n"
        "    fi\n"
        '    if ! COMPOSE_PS_JSON="${output}" python3 - <<\'PY\'; then\n'
        "import json\n"
        "import os\n"
        "import sys\n"
        "\n"
        "raw = os.environ.get('COMPOSE_PS_JSON', '').strip()\n"
        "items = []\n"
        "if raw.startswith('['):\n"
        "    items = json.loads(raw)\n"
        "else:\n"
        "    items = [json.loads(line) for line in raw.splitlines() if line.strip()]\n"
        "bad = []\n"
        "for item in items:\n"
        "    name = item.get('Service') or item.get('Name') or item.get('Names') or '<unknown>'\n"
        "    state = str(item.get('State') or '').lower()\n"
        "    health = str(item.get('Health') or '').lower()\n"
        "    if state and state != 'running':\n"
        "        bad.append(f'{name}: state={state}')\n"
        "        continue\n"
        "    if health and health not in {'healthy', ''}:\n"
        "        bad.append(f'{name}: health={health}')\n"
        "if bad:\n"
        "    print('Unhealthy docker-compose services: ' + ', '.join(bad), file=sys.stderr)\n"
        "    raise SystemExit(1)\n"
        "print('Docker Compose service health check passed.')\n"
        "PY\n"
        "      exit 1\n"
        "    fi\n"
        "    ;;\n"
        "  *)\n"
        '    echo "Unknown health check mode: ${MODE}" >&2\n'
        "    exit 1\n"
        "    ;;\n"
        "esac\n"
    )


def _env_template(manifest: dict) -> str:
    registry = manifest["targetProfile"].get("registry") or "harbor.example.com/local-ai"
    return _env_file(
        manifest,
        {
            "REGISTRY": registry,
            "IMAGE_TAG": "prod",
            "FRONTEND_PORT": "80",
        },
        "envTemplate",
    )


def _secret_string_data(manifest: dict) -> str:
    values: dict[str, str] = {}
    for key in _runtime_middleware_keys(manifest):
        values.update(_middleware_definition(key, manifest).get("envTemplate") or {})
    secret_values = {
        name: value
        for name, value in values.items()
        if "__REPLACE_WITH_" in str(value)
    }
    if not secret_values:
        secret_values = {"DATABASE_PASSWORD": "__REPLACE_WITH_DATABASE_PASSWORD__"}
    return "".join(f"  {name}: {value}\n" for name, value in secret_values.items())


def _env_defaults(manifest: dict) -> str:
    registry = manifest["targetProfile"].get("registry") or "harbor.example.com/local-ai"
    values = {
        "REGISTRY": registry,
        "IMAGE_TAG": "prod",
        "FRONTEND_PORT": "80",
    }
    values.update(manifest.get("_runtimeEnv") or {})
    return _env_file(manifest, values, "envTemplate", keep_existing=True)


def _env_file(manifest: dict, base_values: dict[str, str], field: str, *, keep_existing: bool = False) -> str:
    values = dict(base_values)
    for key in _runtime_middleware_keys(manifest):
        for name, value in (_middleware_definition(key, manifest).get(field) or {}).items():
            if keep_existing and name in values:
                continue
            values[name] = value
    return "".join(f"{name}={value}\n" for name, value in values.items())


def _middleware_definition(key: str, manifest: dict) -> dict:
    return (manifest.get("middlewareConfig") or {}).get(key) or {}


def _middleware_port(key: str, manifest: dict) -> int:
    return int(_middleware_definition(key, manifest).get("port") or DEFAULT_CONTAINER_PORT)


def _middleware_data_path(key: str, manifest: dict) -> str:
    return _middleware_definition(key, manifest).get("dataPath") or f"/var/lib/{key}"


def _join_yaml_docs(docs: list[str]) -> str:
    return "---\n".join(item.rstrip() + "\n" for item in docs if item.strip())


def _service_specs(manifest: dict) -> list[dict]:
    specs: list[dict] = []
    counters = {"platform": 0, "business": 0}
    microservices = _registered_microservices_by_image(manifest)
    for group in ("platform", "business"):
        for image in manifest["images"].get(group, []):
            source_ref = _with_default_tag(image, manifest)
            entry = _image_entry_for_source(manifest, source_ref)
            microservice = microservices.get(source_ref)
            name = _service_name_from_image(image)
            namespace = _base_namespace(manifest) if group == "platform" else _business_namespace(manifest, name)
            port = 80 if "frontend" in name or name.startswith("sub-app") else DEFAULT_CONTAINER_PORT
            business_key = _business_key_for_service(manifest, name) if group == "business" else ""
            if microservice:
                name = _safe_resource_name(str(microservice.get("serviceKey") or name))
                namespace = _microservice_namespace(manifest, microservice)
                port = int(microservice.get("port") or DEFAULT_CONTAINER_PORT)
                business_key = str(microservice.get("businessPlatformKey") or business_key).strip()
            counters[group] += 1
            specs.append(
                {
                    "name": name,
                    "group": group,
                    "image": entry["targetRef"],
                    "namespace": namespace,
                    "port": port,
                    "hostPort": 18080 + (0 if group == "platform" else 100) + counters[group],
                    "businessKey": business_key,
                    "microservice": microservice or None,
                }
            )
    return specs


def _registered_microservices_by_image(manifest: dict) -> dict[str, dict]:
    result: dict[str, dict] = {}
    for service in manifest.get("registeredMicroservices") or []:
        image = str(service.get("image") or "").strip()
        if not image:
            continue
        result[_with_default_tag(image, manifest)] = service
    return result


def _image_entry_for_source(manifest: dict, source_ref: str) -> dict:
    for item in manifest["imageEntries"]:
        if item.get("catalogRef") == source_ref or item["sourceRef"] == source_ref:
            return item
    raise ValueError(f"Image entry not found for {source_ref}.")


def _middleware_image(key: str, manifest: dict) -> str:
    source_ref = _with_default_tag(manifest["databaseImage"], manifest) if key == manifest["database"] else _middleware_source_ref(key, manifest)
    for item in manifest["imageEntries"]:
        if item.get("catalogRef") == source_ref or item["sourceRef"] == source_ref:
            return item["targetRef"]
    return _target_image_ref(source_ref, manifest["targetProfile"].get("registry", ""))


def _runtime_middleware_keys(manifest: dict) -> list[str]:
    keys = [manifest["database"], *manifest["middleware"]]
    return list(dict.fromkeys(keys))


def _middleware_source_ref(key: str, manifest: dict) -> str:
    if key == manifest.get("database"):
        return _with_default_tag(manifest["databaseImage"], manifest)
    for item in manifest["imageEntries"]:
        catalog_ref = item.get("catalogRef") or item["sourceRef"]
        if item["group"] == "middleware" and catalog_ref.startswith(f"{key}:"):
            return catalog_ref
    for item in manifest["imageEntries"]:
        catalog_ref = item.get("catalogRef") or item["sourceRef"]
        if item["group"] == "middleware" and key in catalog_ref:
            return catalog_ref
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
    business = _business_key_for_service(manifest, service_name)
    if business:
        return f"{prefix}-business-{business}"
    fallback = manifest["businessServices"][0] if manifest["businessServices"] else "default"
    return f"{prefix}-business-{fallback}"


def _business_key_for_service(manifest: dict, service_name: str) -> str:
    for business in manifest["businessServices"]:
        if business in service_name:
            return business
    return ""


def _microservice_namespace(manifest: dict, service: dict) -> str:
    business_key = str(service.get("businessPlatformKey") or "").strip()
    if business_key:
        return _business_namespace(manifest, business_key)
    namespace = str(service.get("k8sNamespace") or "").strip()
    if namespace:
        return namespace
    return _business_namespace(manifest, str(service.get("serviceKey") or "default"))


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


def _with_default_tag(image: str, manifest: dict) -> str:
    image = image.strip()
    if not image:
        raise ValueError("Image reference cannot be empty.")
    last_part = image.rsplit("/", 1)[-1]
    if ":" in last_part or "@" in last_part:
        return image
    return f"{image}:{manifest.get('imageTag') or 'prod'}"


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
