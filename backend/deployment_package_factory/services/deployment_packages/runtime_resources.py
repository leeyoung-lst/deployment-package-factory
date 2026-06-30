from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse

from deployment_package_factory.services.deployment_packages.models import PackageBuildRequest


SENSITIVE_NAMES = {"PASSWORD", "SECRET", "TOKEN", "API_KEY", "KEY"}
DATABASE_ENV_NAMES = ("DATABASE_URL", "POSTGRES_DSN", "SPRING_DATASOURCE_URL")
SCHEMA_ENV_NAMES = ("DATABASE_SCHEMA", "POSTGRES_SCHEMA", "SPRING_DATASOURCE_SCHEMA")
MINIO_BUCKET_ENV_NAMES = ("MINIO_BUCKET", "MINIO_BUCKETS", "S3_BUCKET", "DOCUMENT_BUCKET")
QDRANT_COLLECTION_ENV_NAMES = ("QDRANT_COLLECTION", "QDRANT_COLLECTIONS", "VECTOR_COLLECTION")


@dataclass(frozen=True)
class RuntimeEnvProbe:
    service_key: str
    service_name: str
    env: dict[str, str]


def build_runtime_config(
    *,
    request: PackageBuildRequest,
    preview,
    middleware_config: dict,
    runtime_env: dict[str, str],
    probes: list[RuntimeEnvProbe] | None = None,
) -> dict:
    overrides = request.runtime_config_overrides
    env_values = {**runtime_env, **overrides}
    database_resources = _probe_database_resources(request.database or preview.database.key, probes or [], env_values)
    bucket_resources = _probe_bucket_resources(probes or [])
    collection_resources = _probe_collection_resources(probes or [])
    resources = _dedupe_resources(
        [
            *(database_resources or _default_database_resources(request.database or preview.database.key, preview, env_values)),
            *(bucket_resources or _default_bucket_resources(preview)),
            *(collection_resources or _default_collection_resources(preview)),
        ]
    )
    resources = _dedupe_resources([_apply_resource_overrides(resource, overrides) for resource in resources])
    groups = _config_groups(middleware_config, env_values)
    return {
        "groups": groups,
        "resources": resources,
        "overrides": dict(overrides),
    }


def public_runtime_config(runtime_config: dict, *, include_values: bool = False) -> dict:
    return {
        "groups": [
            {
                **group,
                "items": [_public_item(item, include_values=include_values) for item in group.get("items", [])],
            }
            for group in runtime_config.get("groups", [])
        ],
        "resources": [
            {
                **resource,
                "items": [_public_item(item, include_values=include_values) for item in resource.get("items", [])],
            }
            for resource in runtime_config.get("resources", [])
        ],
    }


def runtime_env_from_config(runtime_config: dict) -> dict[str, str]:
    values: dict[str, str] = {}
    for group in runtime_config.get("groups", []):
        for item in group.get("items", []):
            values[str(item["name"])] = str(item.get("value") or "")
    return values


def _config_groups(middleware_config: dict, env_values: dict[str, str]) -> list[dict]:
    groups: list[dict] = []
    for key, definition in middleware_config.items():
        items = []
        for name, fallback in (definition.get("envTemplate") or {}).items():
            value = str(env_values.get(name, fallback))
            items.append(_config_item(name, _label_for(name), value, source="source-secret" if name in env_values else "catalog"))
        if items:
            groups.append({"key": key, "name": definition.get("name") or key, "items": items})
    return groups


def _probe_database_resources(database_key: str, probes: list[RuntimeEnvProbe], env_values: dict[str, str]) -> list[dict]:
    resources: list[dict] = []
    for probe in probes:
        parsed = _parse_database_probe(database_key, probe, env_values)
        if parsed:
            resources.append(parsed)
    return resources


def _parse_database_probe(database_key: str, probe: RuntimeEnvProbe, env_values: dict[str, str]) -> dict | None:
    dsn = _first_env(probe.env, DATABASE_ENV_NAMES)
    if not dsn:
        return None
    parsed = urlparse(_normalize_dsn(dsn))
    database_name = parsed.path.strip("/") or env_values.get("DATABASE_NAME") or "local_ai"
    schema = _first_env(probe.env, SCHEMA_ENV_NAMES) or _schema_from_query(parsed.query) or "public"
    username = parsed.username or probe.env.get("DATABASE_USER") or env_values.get("DATABASE_USER") or "local_ai"
    password = parsed.password or probe.env.get("DATABASE_PASSWORD") or env_values.get("DATABASE_PASSWORD") or ""
    key = _resource_key("databaseSchema", database_key, database_name, schema)
    return _database_resource(key, database_key, database_name, schema, username, password, [probe.service_key], source="pod-env")


def _default_database_resources(database_key: str, preview, env_values: dict[str, str]) -> list[dict]:
    service_keys = _service_keys(preview)
    if not service_keys:
        service_keys = ["platform"]
    database_name = env_values.get("DATABASE_NAME") or env_values.get("DM_DATABASE") or "local_ai"
    schema = env_values.get("DATABASE_SCHEMA") or "public"
    username = env_values.get("DATABASE_USER") or env_values.get("DM_USERNAME") or "local_ai"
    password = env_values.get("DATABASE_PASSWORD") or env_values.get("DM_PASSWORD") or ""
    key = _resource_key("databaseSchema", database_key, database_name, schema)
    return [_database_resource(key, database_key, database_name, schema, username, password, service_keys, source="catalog", needs_review=True)]


def _database_resource(
    key: str,
    database_key: str,
    database_name: str,
    schema: str,
    username: str,
    password: str,
    used_by: list[str],
    *,
    source: str,
    needs_review: bool = False,
) -> dict:
    return {
        "key": key,
        "type": "databaseSchema",
        "name": f"{database_key} {database_name}.{schema}",
        "middlewareKey": database_key,
        "source": source,
        "needsReview": needs_review,
        "shared": len(set(used_by)) > 1,
        "usedBy": list(dict.fromkeys(used_by)),
        "items": [
            _config_item("databaseName", "数据库名", database_name, env_name="DATABASE_NAME", source=source),
            _config_item("schema", "Schema", schema, env_name="DATABASE_SCHEMA", source=source),
            _config_item("username", "用户名", username, env_name="DATABASE_USER", source=source),
            _config_item("password", "密码", password, env_name="DATABASE_PASSWORD", source=source, sensitive=True),
        ],
    }


def _probe_bucket_resources(probes: list[RuntimeEnvProbe]) -> list[dict]:
    resources: list[dict] = []
    for probe in probes:
        for bucket in _split_values(_first_env(probe.env, MINIO_BUCKET_ENV_NAMES)):
            resources.append(_bucket_resource(bucket, [probe.service_key], source="pod-env"))
    return resources


def _default_bucket_resources(preview) -> list[dict]:
    if "minio" not in {item.key for item in preview.middleware}:
        return []
    services = _service_keys(preview)
    buckets = ["platform-documents", *[item.key for item in preview.business_services]]
    return [_bucket_resource(bucket, services or ["platform"], source="catalog", needs_review=True) for bucket in buckets]


def _bucket_resource(bucket: str, used_by: list[str], *, source: str, needs_review: bool = False) -> dict:
    return {
        "key": _resource_key("bucket", "minio", bucket),
        "type": "bucket",
        "name": bucket,
        "middlewareKey": "minio",
        "source": source,
        "needsReview": needs_review,
        "shared": len(set(used_by)) > 1,
        "usedBy": list(dict.fromkeys(used_by)),
        "items": [_config_item("bucket", "Bucket", bucket, source=source)],
    }


def _probe_collection_resources(probes: list[RuntimeEnvProbe]) -> list[dict]:
    resources: list[dict] = []
    for probe in probes:
        for collection in _split_values(_first_env(probe.env, QDRANT_COLLECTION_ENV_NAMES)):
            resources.append(_collection_resource(collection, [probe.service_key], source="pod-env"))
    return resources


def _default_collection_resources(preview) -> list[dict]:
    if "qdrant" not in {item.key for item in preview.middleware}:
        return []
    services = _service_keys(preview)
    collections = ["agent_memory", *[f"{key}_knowledge" for key in services if key]]
    return [_collection_resource(collection, services or ["ai-agent"], source="catalog", needs_review=True) for collection in collections]


def _collection_resource(collection: str, used_by: list[str], *, source: str, needs_review: bool = False) -> dict:
    return {
        "key": _resource_key("collection", "qdrant", collection),
        "type": "collection",
        "name": collection,
        "middlewareKey": "qdrant",
        "source": source,
        "needsReview": needs_review,
        "shared": len(set(used_by)) > 1,
        "usedBy": list(dict.fromkeys(used_by)),
        "items": [
            _config_item("collection", "Collection", collection, source=source),
            _config_item("vectorSize", "向量维度", "1536", source="catalog"),
            _config_item("distance", "距离算法", "Cosine", source="catalog"),
        ],
    }


def _dedupe_resources(resources: list[dict]) -> list[dict]:
    result: dict[str, dict] = {}
    for resource in resources:
        key = resource["key"]
        if key not in result:
            result[key] = resource
            continue
        existing = result[key]
        existing["usedBy"] = list(dict.fromkeys([*existing.get("usedBy", []), *resource.get("usedBy", [])]))
        existing["shared"] = len(existing["usedBy"]) > 1
        existing["needsReview"] = bool(existing.get("needsReview")) and bool(resource.get("needsReview"))
        if existing.get("source") != "pod-env" and resource.get("source") == "pod-env":
            existing["source"] = "pod-env"
            existing["items"] = resource.get("items", existing.get("items", []))
    return sorted(result.values(), key=lambda item: (item["type"], item["key"]))


def _config_item(
    name: str,
    label: str,
    value: str,
    *,
    env_name: str = "",
    source: str,
    sensitive: bool | None = None,
) -> dict:
    is_sensitive = _is_sensitive(name if not env_name else env_name) if sensitive is None else sensitive
    return {
        "name": name,
        "envName": env_name or name,
        "overrideName": env_name or name,
        "label": label,
        "value": value,
        "sensitive": is_sensitive,
        "source": source,
        "resolved": bool(value) and "__REPLACE_WITH_" not in value,
    }


def _apply_resource_overrides(resource: dict, overrides: dict[str, str]) -> dict:
    resource = {**resource}
    updated_items = []
    for item in resource.get("items", []):
        override_name = _resource_override_name(resource["key"], item)
        value = overrides.get(override_name, item.get("value", ""))
        updated_items.append({**item, "overrideName": override_name, "value": value, "resolved": bool(value) and "__REPLACE_WITH_" not in str(value)})
    resource["items"] = updated_items
    if resource.get("type") == "databaseSchema":
        database_name = _item_value(updated_items, "databaseName")
        schema = _item_value(updated_items, "schema")
        if database_name and schema:
            resource["name"] = f"{resource.get('middlewareKey')} {database_name}.{schema}"
            resource["key"] = _resource_key("databaseSchema", resource.get("middlewareKey", ""), database_name, schema)
    elif resource.get("type") in {"bucket", "collection"}:
        name = _item_value(updated_items, "bucket") or _item_value(updated_items, "collection") or resource.get("name", "")
        resource["name"] = name
        resource["key"] = _resource_key(str(resource.get("type")), resource.get("middlewareKey", ""), name)
    return resource


def _resource_override_name(resource_key: str, item: dict) -> str:
    name = str(item.get("name") or "")
    return f"{resource_key}.{name}"


def _item_value(items: list[dict], name: str) -> str:
    for item in items:
        if item.get("name") == name:
            return str(item.get("value") or "")
    return ""


def _public_item(item: dict, *, include_values: bool) -> dict:
    value = str(item.get("value") or "")
    if item.get("sensitive") and not include_values:
        value = "******" if item.get("resolved") else ""
    return {**item, "value": value}


def _label_for(name: str) -> str:
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


def _first_env(env: dict[str, str], names: tuple[str, ...]) -> str:
    for name in names:
        value = env.get(name)
        if value:
            return value
    return ""


def _schema_from_query(query: str) -> str:
    values = parse_qs(query)
    for key in ("currentSchema", "schema", "search_path"):
        if values.get(key):
            return values[key][0]
    return ""


def _normalize_dsn(dsn: str) -> str:
    if dsn.startswith("jdbc:"):
        return dsn[5:]
    return dsn


def _split_values(value: str) -> list[str]:
    return [item.strip() for item in re.split(r"[,;\s]+", value or "") if item.strip()]


def _resource_key(*parts: str) -> str:
    return "-".join(re.sub(r"[^a-z0-9]+", "-", str(part).lower()).strip("-") for part in parts if str(part))


def _service_keys(preview) -> list[str]:
    return list(dict.fromkeys([*[item.key for item in preview.platform_services], *[item.key for item in preview.business_services]]))


def _is_sensitive(name: str) -> bool:
    upper = name.upper()
    return any(marker in upper for marker in SENSITIVE_NAMES)
