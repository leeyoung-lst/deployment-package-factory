from __future__ import annotations

from deployment_package_factory.services.deployment_packages.runtime_env_values import is_resolved_value


SENSITIVE_NAMES = {"PASSWORD", "SECRET", "TOKEN", "API_KEY", "KEY"}


def config_item(
    name: str,
    label: str,
    value: str,
    *,
    env_name: str = "",
    source: str,
    sensitive: bool | None = None,
) -> dict:
    is_sensitive = is_sensitive_name(name if not env_name else env_name) if sensitive is None else sensitive
    return {
        "name": name,
        "envName": env_name or name,
        "overrideName": env_name or name,
        "label": label,
        "value": value,
        "sensitive": is_sensitive,
        "source": source,
        "resolved": is_resolved_value(value),
    }


def public_item(item: dict, *, include_values: bool) -> dict:
    value = str(item.get("value") or "")
    if item.get("sensitive") and not include_values:
        value = "******" if item.get("resolved") else ""
    return {**item, "value": value}


def label_for(name: str) -> str:
    labels = {
        "DATABASE_NAME": "数据库名",
        "DATABASE_USER": "用户名",
        "DATABASE_PASSWORD": "密码",
        "DM_USERNAME": "用户名",
        "DM_PASSWORD": "密码",
        "REDIS_PASSWORD": "密码",
        "MINIO_ROOT_USER": "Root 用户",
        "MINIO_ROOT_PASSWORD": "Root 密码",
        "QDRANT_API_KEY": "API Key",
        "CAMUNDA_ADMIN_USER": "管理员",
        "CAMUNDA_ADMIN_PASSWORD": "管理员密码",
        "IOTDB_USER": "用户名",
        "IOTDB_PASSWORD": "密码",
    }
    return labels.get(name, name)


def is_sensitive_name(name: str) -> bool:
    upper = name.upper()
    return any(marker in upper for marker in SENSITIVE_NAMES)
