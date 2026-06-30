from __future__ import annotations

import re
from collections.abc import Callable
from urllib.parse import urlparse

import yaml

from deployment_package_factory.services.deployment_packages.runtime_env_aliases import runtime_env_alias, runtime_env_alias_for_source
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
            spec = pod.get("spec") or {}
            for container in spec.get("containers", []):
                env = _container_env(namespace, container, spec.get("volumes", []), secret_reader, configmap_reader)
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
    volumes: list[dict],
    secret_reader: ResourceReader,
    configmap_reader: ResourceReader,
) -> dict[str, str]:
    values: dict[str, str] = {}
    for source in container.get("envFrom") or []:
        secret_name = ((source.get("secretRef") or {}).get("name") or "").strip()
        configmap_name = ((source.get("configMapRef") or {}).get("name") or "").strip()
        if secret_name:
            values.update(_runtime_config_values(secret_reader(namespace, secret_name), secret_name))
        if configmap_name:
            values.update(_runtime_config_values(configmap_reader(namespace, configmap_name), configmap_name))
    for item in container.get("env") or []:
        _apply_env_item(values, namespace, item, secret_reader, configmap_reader)
    for source_type, source_name, keys in _mounted_sources(container, volumes):
        reader = secret_reader if source_type == "secret" else configmap_reader
        values.update(_runtime_config_values(_filter_keys(reader(namespace, source_name), keys), source_name))
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


def _runtime_config_values(values: dict[str, str], source_name: str = "") -> dict[str, str]:
    result: dict[str, str] = {}
    for key, value in values.items():
        _set_runtime_value(result, key, value, source_name)
    for content in values.values():
        result.update(_runtime_values_from_text(content))
    return {key: value for key, value in result.items() if value}


def _set_runtime_value(values: dict[str, str], key: str, value: str, source_name: str = "") -> None:
    normalized = _runtime_env_key(key, source_name)
    if not normalized or not value:
        return
    if normalized == "REDIS_URL":
        password = _url_credentials(value)[1]
        if password:
            values["REDIS_PASSWORD"] = password
        return
    if normalized == "IOTDB_URL":
        username, password = _url_credentials(value)
        if username:
            values["IOTDB_USER"] = username
        if password:
            values["IOTDB_PASSWORD"] = password
        return
    if normalized:
        values[normalized] = str(value)


def _runtime_values_from_text(content: str) -> dict[str, str]:
    if not content:
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
    values.update(_runtime_values_from_yaml(content))
    return values


def _runtime_values_from_yaml(content: str) -> dict[str, str]:
    try:
        payload = yaml.safe_load(content)
    except yaml.YAMLError:
        return {}
    if not isinstance(payload, dict):
        return {}
    values: dict[str, str] = {}
    for key, value in _flatten_yaml("", payload):
        _set_runtime_value(values, key, value)
    return values


def _flatten_yaml(prefix: str, value) -> list[tuple[str, str]]:
    if isinstance(value, dict):
        result: list[tuple[str, str]] = []
        for key, nested in value.items():
            name = f"{prefix}.{key}" if prefix else str(key)
            result.extend(_flatten_yaml(name, nested))
        return result
    if isinstance(value, list):
        scalar_values = [str(item) for item in value if not isinstance(item, (dict, list)) and item is not None]
        return [(prefix, ",".join(scalar_values))] if scalar_values else []
    if value is None:
        return []
    return [(prefix, str(value))]


def _mounted_sources(container: dict, volumes: list[dict]) -> list[tuple[str, str, set[str] | None]]:
    volume_refs = {str(volume.get("name") or ""): volume for volume in volumes}
    sources: list[tuple[str, str, set[str]]] = []
    for mount in container.get("volumeMounts") or []:
        volume = volume_refs.get(str(mount.get("name") or ""))
        if not volume:
            continue
        source_type, source_name, keys, path_keys = _volume_source(volume)
        if source_name:
            sources.append((source_type, source_name, _mount_keys(mount, keys, path_keys)))
    return sources


def _volume_source(volume: dict) -> tuple[str, str, set[str] | None, dict[str, str]]:
    config_map = volume.get("configMap") or {}
    if config_map.get("name"):
        return "configmap", str(config_map["name"]), _volume_item_keys(config_map), _volume_item_path_keys(config_map)
    secret = volume.get("secret") or {}
    if secret.get("secretName"):
        return "secret", str(secret["secretName"]), _volume_item_keys(secret), _volume_item_path_keys(secret)
    return "", "", None, {}


def _volume_item_keys(source: dict) -> set[str] | None:
    items = source.get("items")
    if not items:
        return None
    return {str(item.get("key")) for item in items if item.get("key")}


def _volume_item_path_keys(source: dict) -> dict[str, str]:
    result: dict[str, str] = {}
    for item in source.get("items") or []:
        key = str(item.get("key") or "")
        if not key:
            continue
        result[key] = key
        result[str(item.get("path") or key)] = key
    return result


def _mount_keys(mount: dict, volume_keys: set[str] | None, path_keys: dict[str, str]) -> set[str] | None:
    sub_path = str(mount.get("subPath") or "").strip()
    if not sub_path:
        return volume_keys
    if path_keys:
        key = path_keys.get(sub_path)
        return {key} if key else set()
    return {sub_path}


def _filter_keys(values: dict[str, str], keys: set[str] | None) -> dict[str, str]:
    if keys is None:
        return values
    return {key: value for key, value in values.items() if key in keys}


def _runtime_env_key(key: str, source_name: str = "") -> str:
    normalized = re.sub(r"[^A-Za-z0-9]+", "_", key).strip("_").upper()
    return runtime_env_alias(normalized) or runtime_env_alias_for_source(source_name, key)


def _service_key_from_pod(pod: dict, container: dict) -> str:
    labels = (pod.get("metadata") or {}).get("labels") or {}
    for key in ("app.kubernetes.io/name", "app", "local-ai.io/product"):
        if labels.get(key):
            return str(labels[key])
    name = container.get("name") or (pod.get("metadata") or {}).get("name") or "service"
    return str(name)


def _url_credentials(value: str) -> tuple[str, str]:
    parsed = urlparse(value[5:] if value.startswith("jdbc:") else value)
    return parsed.username or "", parsed.password or ""
