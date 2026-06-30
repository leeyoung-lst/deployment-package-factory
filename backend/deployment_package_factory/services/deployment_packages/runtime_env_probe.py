from __future__ import annotations

from collections.abc import Callable

from deployment_package_factory.services.deployment_packages.runtime_env_parser import runtime_config_values, set_runtime_value
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
            values.update(runtime_config_values(secret_reader(namespace, secret_name), secret_name))
        if configmap_name:
            values.update(runtime_config_values(configmap_reader(namespace, configmap_name), configmap_name))
    for item in container.get("env") or []:
        _apply_env_item(values, namespace, item, secret_reader, configmap_reader)
    for source_type, source_name, keys in _mounted_sources(container, volumes):
        reader = secret_reader if source_type == "secret" else configmap_reader
        values.update(runtime_config_values(_filter_keys(reader(namespace, source_name), keys), source_name))
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
        set_runtime_value(values, name, str(item.get("value") or ""))
        return
    value_from = item.get("valueFrom") or {}
    secret_ref = value_from.get("secretKeyRef") or {}
    if secret_ref.get("name") and secret_ref.get("key"):
        source_name = str(secret_ref["name"])
        _set_referenced_runtime_value(values, name, str(secret_ref["key"]), secret_reader(namespace, source_name).get(str(secret_ref["key"]), ""), source_name)
        return
    configmap_ref = value_from.get("configMapKeyRef") or {}
    if configmap_ref.get("name") and configmap_ref.get("key"):
        source_name = str(configmap_ref["name"])
        _set_referenced_runtime_value(values, name, str(configmap_ref["key"]), configmap_reader(namespace, source_name).get(str(configmap_ref["key"]), ""), source_name)


def _set_referenced_runtime_value(values: dict[str, str], env_name: str, ref_key: str, value: str, source_name: str) -> None:
    if not set_runtime_value(values, env_name, value, source_name):
        set_runtime_value(values, ref_key, value, source_name)


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


def _service_key_from_pod(pod: dict, container: dict) -> str:
    labels = (pod.get("metadata") or {}).get("labels") or {}
    for key in ("app.kubernetes.io/name", "app", "local-ai.io/product"):
        if labels.get(key):
            return str(labels[key])
    name = container.get("name") or (pod.get("metadata") or {}).get("name") or "service"
    return str(name)
