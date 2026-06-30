from __future__ import annotations

from urllib.parse import urlparse

import yaml

from deployment_package_factory.services.deployment_packages.runtime_env_aliases import runtime_env_alias, runtime_env_alias_for_source


def set_runtime_value(values: dict[str, str], key: str, value: str, source_name: str = "") -> bool:
    normalized = runtime_env_key(key, source_name)
    if not normalized or not value:
        return False
    if normalized == "REDIS_URL":
        password = _url_credentials(value)[1]
        if password:
            values["REDIS_PASSWORD"] = password
            return True
        return False
    if normalized == "IOTDB_URL":
        username, password = _url_credentials(value)
        if username:
            values["IOTDB_USER"] = username
        if password:
            values["IOTDB_PASSWORD"] = password
        return bool(username or password)
    values[normalized] = str(value)
    return True


def runtime_config_values(values: dict[str, str], source_name: str = "") -> dict[str, str]:
    result: dict[str, str] = {}
    for key, value in values.items():
        set_runtime_value(result, key, value, source_name)
    for content in values.values():
        result.update(runtime_values_from_text(content, source_name))
    return {key: value for key, value in result.items() if value}


def runtime_values_from_text(content: str, source_name: str = "") -> dict[str, str]:
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
        set_runtime_value(values, key.strip(), value.strip().strip("\"'"), source_name)
    values.update(_runtime_values_from_yaml(content, source_name))
    return values


def runtime_env_key(key: str, source_name: str = "") -> str:
    normalized = runtime_env_alias_for_source(source_name, key)
    return normalized or runtime_env_alias(runtime_env_alias_normalize(key))


def runtime_env_alias_normalize(value: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in value).strip("_").upper()


def _runtime_values_from_yaml(content: str, source_name: str = "") -> dict[str, str]:
    try:
        payload = yaml.safe_load(content)
    except yaml.YAMLError:
        return {}
    if not isinstance(payload, dict):
        return {}
    values: dict[str, str] = {}
    for key, value in _flatten_yaml("", payload):
        set_runtime_value(values, key, value, source_name)
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


def _url_credentials(value: str) -> tuple[str, str]:
    parsed = urlparse(value[5:] if value.startswith("jdbc:") else value)
    return parsed.username or "", parsed.password or ""
