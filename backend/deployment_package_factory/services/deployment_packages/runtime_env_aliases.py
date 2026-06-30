from __future__ import annotations

import re

RUNTIME_ENV_ALIASES = {
    "DB_NAME": "DATABASE_NAME",
    "DB_DATABASE": "DATABASE_NAME",
    "POSTGRES_DB": "DATABASE_NAME",
    "POSTGRES_DATABASE": "DATABASE_NAME",
    "POSTGRESQL_DATABASE": "DATABASE_NAME",
    "DM_DATABASE": "DATABASE_NAME",
    "DB_URL": "DATABASE_URL",
    "DATASOURCE_URL": "DATABASE_URL",
    "SPRING_DATASOURCE_URL": "DATABASE_URL",
    "POSTGRES_URL": "DATABASE_URL",
    "POSTGRESQL_URL": "DATABASE_URL",
    "DB_USER": "DATABASE_USER",
    "DB_USERNAME": "DATABASE_USER",
    "DATASOURCE_USERNAME": "DATABASE_USER",
    "DATASOURCE_USER": "DATABASE_USER",
    "SPRING_DATASOURCE_USERNAME": "DATABASE_USER",
    "POSTGRES_USER": "DATABASE_USER",
    "POSTGRES_USERNAME": "DATABASE_USER",
    "POSTGRESQL_USER": "DATABASE_USER",
    "POSTGRESQL_USERNAME": "DATABASE_USER",
    "DM_USERNAME": "DATABASE_USER",
    "DB_PASSWORD": "DATABASE_PASSWORD",
    "DATASOURCE_PASSWORD": "DATABASE_PASSWORD",
    "SPRING_DATASOURCE_PASSWORD": "DATABASE_PASSWORD",
    "POSTGRES_PASSWORD": "DATABASE_PASSWORD",
    "POSTGRESQL_PASSWORD": "DATABASE_PASSWORD",
    "DM_PASSWORD": "DATABASE_PASSWORD",
    "SPRING_DATASOURCE_SCHEMA": "DATABASE_SCHEMA",
    "SPRING_DATASOURCE_HIKARI_SCHEMA": "DATABASE_SCHEMA",
    "SPRING_JPA_PROPERTIES_HIBERNATE_DEFAULT_SCHEMA": "DATABASE_SCHEMA",
    "DB_SCHEMA": "DATABASE_SCHEMA",
    "POSTGRES_DSN": "POSTGRES_DSN",
    "POSTGRES_SCHEMA": "POSTGRES_SCHEMA",
    "POSTGRESQL_SCHEMA": "POSTGRES_SCHEMA",
    "MINIO_BUCKET": "MINIO_BUCKET",
    "MINIO_DEFAULT_BUCKET": "MINIO_BUCKET",
    "MINIO_BUCKET_NAME": "MINIO_BUCKET",
    "MINIO_BUCKETS": "MINIO_BUCKETS",
    "S3_BUCKET": "S3_BUCKET",
    "S3_BUCKET_NAME": "S3_BUCKET",
    "DOCUMENT_BUCKET": "DOCUMENT_BUCKET",
    "DOCUMENTS_BUCKET": "DOCUMENT_BUCKET",
    "FILE_BUCKET": "DOCUMENT_BUCKET",
    "OSS_BUCKET": "DOCUMENT_BUCKET",
    "QDRANT_COLLECTION": "QDRANT_COLLECTION",
    "QDRANT_COLLECTION_NAME": "QDRANT_COLLECTION",
    "QDRANT_COLLECTIONS": "QDRANT_COLLECTIONS",
    "VECTOR_COLLECTION": "VECTOR_COLLECTION",
    "VECTOR_COLLECTION_NAME": "VECTOR_COLLECTION",
    "REDIS_URL": "REDIS_URL",
    "REDIS_URI": "REDIS_URL",
    "SPRING_REDIS_URL": "REDIS_URL",
    "SPRING_DATA_REDIS_URL": "REDIS_URL",
    "REDIS_PASSWORD": "REDIS_PASSWORD",
    "REDIS_REQUIREPASS": "REDIS_PASSWORD",
    "REDIS_AUTH": "REDIS_PASSWORD",
    "SPRING_DATA_REDIS_PASSWORD": "REDIS_PASSWORD",
    "SPRING_REDIS_PASSWORD": "REDIS_PASSWORD",
    "MINIO_ROOT_USER": "MINIO_ROOT_USER",
    "MINIO_ACCESS_KEY": "MINIO_ROOT_USER",
    "MINIO_ROOT_PASSWORD": "MINIO_ROOT_PASSWORD",
    "MINIO_SECRET_KEY": "MINIO_ROOT_PASSWORD",
    "QDRANT_API_KEY": "QDRANT_API_KEY",
    "QDRANT_SERVICE_API_KEY": "QDRANT_API_KEY",
    "QDRANT_SERVICE_APIKEY": "QDRANT_API_KEY",
    "QDRANT__SERVICE__API_KEY": "QDRANT_API_KEY",
    "QDRANT__SERVICE__APIKEY": "QDRANT_API_KEY",
    "VECTOR_API_KEY": "QDRANT_API_KEY",
    "VECTOR_APIKEY": "QDRANT_API_KEY",
    "IOTDB_URL": "IOTDB_URL",
    "IOTDB_URI": "IOTDB_URL",
    "IOTDB_USER": "IOTDB_USER",
    "IOTDB_USERNAME": "IOTDB_USER",
    "IOTDB_PASSWORD": "IOTDB_PASSWORD",
    "EAM_IOTDB_PASSWORD": "IOTDB_PASSWORD",
    "CAMUNDA_ADMIN_USER": "CAMUNDA_ADMIN_USER",
    "CAMUNDA_ADMIN_PASSWORD": "CAMUNDA_ADMIN_PASSWORD",
}

CANONICAL_RUNTIME_ENV_NAMES = {
    "DATABASE_NAME",
    "DATABASE_URL",
    "DATABASE_USER",
    "DATABASE_PASSWORD",
    "DATABASE_SCHEMA",
    "REDIS_PASSWORD",
    "MINIO_ROOT_USER",
    "MINIO_ROOT_PASSWORD",
    "QDRANT_API_KEY",
    "IOTDB_USER",
    "IOTDB_PASSWORD",
    "CAMUNDA_ADMIN_USER",
    "CAMUNDA_ADMIN_PASSWORD",
}

DATABASE_SOURCE_MARKERS = ("POSTGRES", "POSTGRESQL", "DATABASE")
QDRANT_SOURCE_MARKERS = ("QDRANT", "VECTOR")


def runtime_env_alias(normalized: str) -> str:
    if normalized in RUNTIME_ENV_ALIASES:
        return RUNTIME_ENV_ALIASES[normalized]
    return normalized if normalized in CANONICAL_RUNTIME_ENV_NAMES else ""


def runtime_env_alias_for_source(source_name: str, key: str) -> str:
    normalized_key = _normalize(key)
    direct = runtime_env_alias(normalized_key)
    if direct:
        return direct
    source = _normalize(source_name)
    return (
        _database_source_alias(normalized_key, source)
        or _resource_source_alias(normalized_key, source)
        or _url_source_alias(normalized_key, source)
        or _user_source_alias(normalized_key, source)
        or _password_source_alias(normalized_key, source)
    )


def _database_source_alias(normalized_key: str, source: str) -> str:
    if normalized_key in {"SCHEMA", "DATABASE_SCHEMA", "DB_SCHEMA"} and _has_any(source, DATABASE_SOURCE_MARKERS):
        return "DATABASE_SCHEMA"
    if normalized_key in {"DATABASE", "DB", "NAME"} and _has_any(source, DATABASE_SOURCE_MARKERS):
        return "DATABASE_NAME"
    return ""


def _resource_source_alias(normalized_key: str, source: str) -> str:
    if normalized_key in {"BUCKET", "BUCKET_NAME", "DEFAULT_BUCKET"}:
        return _bucket_alias(source)
    if normalized_key in {"BUCKETS", "BUCKET_NAMES"} and "MINIO" in source:
        return "MINIO_BUCKETS"
    if normalized_key in {"COLLECTION", "COLLECTION_NAME"} and _has_any(source, QDRANT_SOURCE_MARKERS):
        return "QDRANT_COLLECTION"
    if normalized_key in {"COLLECTIONS", "COLLECTION_NAMES"} and _has_any(source, QDRANT_SOURCE_MARKERS):
        return "QDRANT_COLLECTIONS"
    return ""


def _url_source_alias(normalized_key: str, source: str) -> str:
    if normalized_key not in {"URL", "URI"}:
        return ""
    if "REDIS" in source:
        return "REDIS_URL"
    if "IOTDB" in source:
        return "IOTDB_URL"
    if _has_any(source, DATABASE_SOURCE_MARKERS):
        return "DATABASE_URL"
    return ""


def _user_source_alias(normalized_key: str, source: str) -> str:
    if normalized_key == "ROOT_USER" and "MINIO" in source:
        return "MINIO_ROOT_USER"
    if normalized_key == "ADMIN_USER" and "CAMUNDA" in source:
        return "CAMUNDA_ADMIN_USER"
    if normalized_key not in {"USER", "USERNAME"}:
        return ""
    if "IOTDB" in source:
        return "IOTDB_USER"
    if "CAMUNDA" in source:
        return "CAMUNDA_ADMIN_USER"
    if "MINIO" in source:
        return "MINIO_ROOT_USER"
    if _has_any(source, DATABASE_SOURCE_MARKERS):
        return "DATABASE_USER"
    return ""


def _password_source_alias(normalized_key: str, source: str) -> str:
    if normalized_key not in {"PASSWORD", "ROOT_PASSWORD", "ADMIN_PASSWORD", "API_KEY"}:
        return ""
    if "REDIS" in source:
        return "REDIS_PASSWORD"
    if "MINIO" in source:
        return "MINIO_ROOT_PASSWORD"
    if _has_any(source, QDRANT_SOURCE_MARKERS):
        return "QDRANT_API_KEY"
    if "IOTDB" in source:
        return "IOTDB_PASSWORD"
    if "CAMUNDA" in source:
        return "CAMUNDA_ADMIN_PASSWORD"
    if _has_any(source, DATABASE_SOURCE_MARKERS):
        return "DATABASE_PASSWORD"
    return ""


def _bucket_alias(source: str) -> str:
    if "MINIO" in source:
        return "MINIO_BUCKET"
    if "S3" in source:
        return "S3_BUCKET"
    if "DOCUMENT" in source or "OSS" in source:
        return "DOCUMENT_BUCKET"
    return ""


def _has_any(value: str, markers: tuple[str, ...]) -> bool:
    return any(marker in value for marker in markers)


def _normalize(value: str) -> str:
    camel_split = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", value)
    return re.sub(r"[^A-Za-z0-9]+", "_", camel_split).strip("_").upper()
