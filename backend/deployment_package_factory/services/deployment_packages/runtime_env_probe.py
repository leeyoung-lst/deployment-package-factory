from __future__ import annotations

import re
from collections.abc import Callable

from deployment_package_factory.services.deployment_packages.runtime_resources import RuntimeEnvProbe


NamespaceResolver = Callable[[str, list[str] | None], list[str]]
PodReader = Callable[[str], dict]
ResourceReader = Callable[[str, str], dict[str, str]]


def runtime_env_probes(
    source_env: str,
    business_namespaces: list[str] | None,
    *,
    namespace_resolver: NamespaceResolver,
    pod_reader: PodReader,
    secret_reader: ResourceReader,
    configmap_reader: ResourceReader,
) -> list[RuntimeEnvProbe]:
    namespaces = _source_namespaces(source_env, business_namespaces, namespace_resolver)
    probes: list[RuntimeEnvProbe] = []
    for namespace in namespaces:
        payload = pod_reader(namespace)
        for pod in payload.get("items", []):
            for container in (pod.get("spec") or {}).get("containers", []):
                env = _container_env(namespace, container, secret_reader, configmap_reader)
                if env:
                    probes.append(
                        RuntimeEnvProbe(
                            service_key=_service_key_from_pod(pod, container),
                            service_name=container.get("name") or (pod.get("metadata") or {}).get("name", ""),
                            env=env,
                        )
                    )
    return probes


def _source_namespaces(source_env: str, business_namespaces: list[str] | None, resolver: NamespaceResolver) -> list[str]:
    try:
        return resolver(source_env, business_namespaces)
    except TypeError:
        return resolver(source_env)  # type: ignore[misc]


def _container_env(
    namespace: str,
    container: dict,
    secret_reader: ResourceReader,
    configmap_reader: ResourceReader,
) -> dict[str, str]:
    values: dict[str, str] = {}
    for source in container.get("envFrom") or []:
        secret_name = ((source.get("secretRef") or {}).get("name") or "").strip()
        configmap_name = ((source.get("configMapRef") or {}).get("name") or "").strip()
        if secret_name:
            values.update(_runtime_config_values(secret_reader(namespace, secret_name)))
        if configmap_name:
            values.update(_runtime_config_values(configmap_reader(namespace, configmap_name)))
    for item in container.get("env") or []:
        _apply_env_item(values, namespace, item, secret_reader, configmap_reader)
    return {key: value for key, value in values.items() if value}


def _apply_env_item(
    values: dict[str, str],
    namespace: str,
    item: dict,
    secret_reader: ResourceReader,
    configmap_reader: ResourceReader,
) -> None:
    name = str(item.get("name") or "")
    if not name:
        return
    if "value" in item:
        _set_runtime_value(values, name, str(item.get("value") or ""))
        return
    value_from = item.get("valueFrom") or {}
    secret_ref = value_from.get("secretKeyRef") or {}
    if secret_ref.get("name") and secret_ref.get("key"):
        _set_runtime_value(values, name, secret_reader(namespace, str(secret_ref["name"])).get(str(secret_ref["key"]), ""))
        return
    configmap_ref = value_from.get("configMapKeyRef") or {}
    if configmap_ref.get("name") and configmap_ref.get("key"):
        _set_runtime_value(values, name, configmap_reader(namespace, str(configmap_ref["name"])).get(str(configmap_ref["key"]), ""))


def _runtime_config_values(values: dict[str, str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for key, value in values.items():
        _set_runtime_value(result, key, value)
    for content in values.values():
        result.update(_runtime_values_from_text(content))
    return {key: value for key, value in result.items() if value}


def _set_runtime_value(values: dict[str, str], key: str, value: str) -> None:
    normalized = _runtime_env_key(key)
    if normalized and value:
        values[normalized] = str(value)


def _runtime_values_from_text(content: str) -> dict[str, str]:
    if not content or "\n" not in content:
        return {}
    values: dict[str, str] = {}
    for raw in content.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        separator = "=" if "=" in line else (":" if ":" in line else "")
        if not separator:
            continue
        key, value = line.split(separator, 1)
        normalized = _runtime_env_key(key.strip())
        if normalized:
            values[normalized] = value.strip().strip("\"'")
    return values


def _runtime_env_key(key: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9]+", "_", key).strip("_").upper()
    aliases = {
        "SPRING_DATASOURCE_URL": "DATABASE_URL",
        "SPRING_DATASOURCE_USERNAME": "DATABASE_USER",
        "SPRING_DATASOURCE_PASSWORD": "DATABASE_PASSWORD",
        "SPRING_DATASOURCE_SCHEMA": "DATABASE_SCHEMA",
        "POSTGRES_DSN": "POSTGRES_DSN",
        "POSTGRES_SCHEMA": "POSTGRES_SCHEMA",
        "MINIO_BUCKET": "MINIO_BUCKET",
        "MINIO_BUCKETS": "MINIO_BUCKETS",
        "S3_BUCKET": "S3_BUCKET",
        "DOCUMENT_BUCKET": "DOCUMENT_BUCKET",
        "QDRANT_COLLECTION": "QDRANT_COLLECTION",
        "QDRANT_COLLECTIONS": "QDRANT_COLLECTIONS",
        "VECTOR_COLLECTION": "VECTOR_COLLECTION",
    }
    if normalized in aliases:
        return aliases[normalized]
    if normalized in {"DATABASE_URL", "DATABASE_USER", "DATABASE_PASSWORD", "DATABASE_SCHEMA"}:
        return normalized
    return ""


def _service_key_from_pod(pod: dict, container: dict) -> str:
    labels = (pod.get("metadata") or {}).get("labels") or {}
    for key in ("app.kubernetes.io/name", "app", "local-ai.io/product"):
        if labels.get(key):
            return str(labels[key])
    name = container.get("name") or (pod.get("metadata") or {}).get("name") or "service"
    return str(name)
