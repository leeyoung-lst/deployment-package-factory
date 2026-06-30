from __future__ import annotations

from deployment_package_factory.services.deployment_packages.runtime_env_probe import runtime_env_probes


def test_runtime_env_probes_maps_secret_key_refs_by_source_name() -> None:
    probes = _probe_with(
        pod_env=[
            {"name": "PASSWORD", "valueFrom": {"secretKeyRef": {"name": "redis-secret", "key": "password"}}},
            {"name": "USERNAME", "valueFrom": {"secretKeyRef": {"name": "iotdb-secret", "key": "username"}}},
            {"name": "PASSWORD", "valueFrom": {"secretKeyRef": {"name": "iotdb-secret", "key": "password"}}},
        ],
        secrets={
            "redis-secret": {"password": "redis-ref-password"},
            "iotdb-secret": {"username": "root", "password": "iotdb-ref-password"},
        },
    )

    assert probes[0].env["REDIS_PASSWORD"] == "redis-ref-password"
    assert probes[0].env["IOTDB_USER"] == "root"
    assert probes[0].env["IOTDB_PASSWORD"] == "iotdb-ref-password"


def test_runtime_env_probes_uses_secret_key_when_env_name_is_generic() -> None:
    probes = _probe_with(
        pod_env=[{"name": "PASSWORD", "valueFrom": {"secretKeyRef": {"name": "app-secret", "key": "redis-password"}}}],
        secrets={"app-secret": {"redis-password": "redis-key-password"}},
    )

    assert probes[0].env["REDIS_PASSWORD"] == "redis-key-password"


def test_runtime_env_probes_extracts_credentials_from_properties_urls() -> None:
    probes = _probe_with(
        env_from=[{"configMapRef": {"name": "redis-config"}}, {"configMapRef": {"name": "iotdb-config"}}],
        configmaps={
            "redis-config": {"application.properties": "url=redis://:redis-url-password@redis:6379/0"},
            "iotdb-config": {"application.properties": "uri=iotdb://root:iotdb-url-password@iotdb:6667"},
        },
    )

    assert probes[0].env["REDIS_PASSWORD"] == "redis-url-password"
    assert probes[0].env["IOTDB_USER"] == "root"
    assert probes[0].env["IOTDB_PASSWORD"] == "iotdb-url-password"


def test_runtime_env_probes_maps_generic_database_config_by_source_name() -> None:
    probes = _probe_with(
        env_from=[{"secretRef": {"name": "postgres-secret"}}],
        secrets={
            "postgres-secret": {
                "url": "postgresql://generic-user:generic-password@postgres:5432/generic_db?currentSchema=eam",
                "database": "generic_db",
                "schema": "eam",
                "username": "generic-user",
                "password": "generic-password",
            }
        },
    )

    assert probes[0].env["DATABASE_URL"].startswith("postgresql://generic-user")
    assert probes[0].env["DATABASE_NAME"] == "generic_db"
    assert probes[0].env["DATABASE_SCHEMA"] == "eam"
    assert probes[0].env["DATABASE_USER"] == "generic-user"
    assert probes[0].env["DATABASE_PASSWORD"] == "generic-password"


def test_runtime_env_probes_maps_generic_bucket_and_vector_config_by_source_name() -> None:
    probes = _probe_with(
        env_from=[{"configMapRef": {"name": "minio-config"}}, {"configMapRef": {"name": "vector-config"}}],
        configmaps={
            "minio-config": {"bucket": "eam-docs", "rootUser": "local-ai", "rootPassword": "minio-password"},
            "vector-config": {"collection": "eam_memory", "apiKey": "qdrant-api-key"},
        },
    )

    assert probes[0].env["MINIO_BUCKET"] == "eam-docs"
    assert probes[0].env["MINIO_ROOT_USER"] == "local-ai"
    assert probes[0].env["MINIO_ROOT_PASSWORD"] == "minio-password"
    assert probes[0].env["QDRANT_COLLECTION"] == "eam_memory"
    assert probes[0].env["QDRANT_API_KEY"] == "qdrant-api-key"


def _probe_with(
    *,
    pod_env: list[dict] | None = None,
    env_from: list[dict] | None = None,
    secrets: dict[str, dict[str, str]] | None = None,
    configmaps: dict[str, dict[str, str]] | None = None,
):
    return runtime_env_probes(
        "test",
        None,
        namespace_resolver=lambda source_env, business_namespaces=None: ["test-base-public"],
        pod_reader=lambda namespace: {
            "items": [
                {
                    "metadata": {"name": "middleware-client-0", "labels": {"app": "middleware-client"}},
                    "spec": {"containers": [{"name": "middleware-client", "env": pod_env or [], "envFrom": env_from or []}]},
                }
            ]
        },
        secret_reader=lambda namespace, name: (secrets or {}).get(name, {}),
        configmap_reader=lambda namespace, name: (configmaps or {}).get(name, {}),
    )
