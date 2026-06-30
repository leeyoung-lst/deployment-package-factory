from __future__ import annotations

from deployment_package_factory.services.deployment_packages.runtime_env_probe import runtime_env_probes


def test_runtime_env_probes_collect_env_from_and_configmap_refs() -> None:
    def pod_reader(namespace: str) -> dict:
        return {
            "items": [
                {
                    "metadata": {"name": "agent-0", "labels": {"app": "ai-agent"}},
                    "spec": {
                        "containers": [
                            {
                                "name": "agent",
                                "envFrom": [
                                    {"secretRef": {"name": "agent-secret"}},
                                    {"configMapRef": {"name": "agent-config"}},
                                ],
                                "env": [
                                    {"name": "QDRANT_COLLECTION", "valueFrom": {"configMapKeyRef": {"name": "agent-config", "key": "collection"}}},
                                ],
                            }
                        ]
                    },
                }
            ]
        }

    probes = runtime_env_probes(
        "test",
        None,
        namespace_resolver=lambda source_env, business_namespaces=None: ["test-base-public"],
        pod_reader=pod_reader,
        secret_reader=lambda namespace, name: {"DATABASE_PASSWORD": "secret-db-password"},
        configmap_reader=lambda namespace, name: {
            "spring.datasource.schema": "agent",
            "application.properties": (
                "spring.datasource.url=postgresql://agent:pw@postgres:5432/ai_agent?currentSchema=agent\n"
                "spring.datasource.username=agent\n"
                "document.bucket=agent-docs\n"
            ),
            "collection": "agent_memory",
        },
    )

    assert probes[0].service_key == "ai-agent"
    assert probes[0].env["DATABASE_URL"].endswith("currentSchema=agent")
    assert probes[0].env["DATABASE_USER"] == "agent"
    assert probes[0].env["DATABASE_PASSWORD"] == "secret-db-password"
    assert probes[0].env["DATABASE_SCHEMA"] == "agent"
    assert probes[0].env["DOCUMENT_BUCKET"] == "agent-docs"
    assert probes[0].env["QDRANT_COLLECTION"] == "agent_memory"


def test_runtime_env_probes_supports_legacy_single_arg_namespace_resolver() -> None:
    probes = runtime_env_probes(
        "test",
        None,
        namespace_resolver=lambda source_env: ["local-ai"],
        pod_reader=lambda namespace: {
            "items": [
                {
                    "metadata": {"name": "eam-0", "labels": {"app.kubernetes.io/name": "eam"}},
                    "spec": {"containers": [{"name": "eam", "env": [{"name": "DATABASE_URL", "value": "postgresql://u:p@db:5432/eam"}]}]},
                }
            ]
        },
        secret_reader=lambda namespace, name: {},
        configmap_reader=lambda namespace, name: {},
    )

    assert probes[0].service_key == "eam"
    assert probes[0].env["DATABASE_URL"] == "postgresql://u:p@db:5432/eam"


def test_runtime_env_probes_collect_nested_yaml_and_mounted_sources() -> None:
    def pod_reader(namespace: str) -> dict:
        return {
            "items": [
                {
                    "metadata": {"name": "iam-0", "labels": {"app": "iam"}},
                    "spec": {
                        "volumes": [
                            {"name": "app-config", "configMap": {"name": "iam-config", "items": [{"key": "application.yml"}]}},
                            {"name": "app-secret", "secret": {"secretName": "iam-secret", "items": [{"key": "db-password"}]}},
                        ],
                        "containers": [
                            {
                                "name": "iam",
                                "volumeMounts": [
                                    {"name": "app-config", "mountPath": "/config"},
                                    {"name": "app-secret", "mountPath": "/secret"},
                                ],
                            }
                        ],
                    },
                }
            ]
        }

    probes = runtime_env_probes(
        "test",
        None,
        namespace_resolver=lambda source_env, business_namespaces=None: ["test-base-public"],
        pod_reader=pod_reader,
        secret_reader=lambda namespace, name: {"db-password": "mounted-secret"},
        configmap_reader=lambda namespace, name: {
            "application.yml": """
spring:
  datasource:
    url: jdbc:postgresql://postgres:5432/local_ai?currentSchema=iam
    username: iam_user
    hikari:
      schema: iam
document:
  bucket: iam-docs
qdrant:
  collection-name: iam_memory
"""
        },
    )

    assert probes[0].env["DATABASE_URL"].startswith("jdbc:postgresql://")
    assert probes[0].env["DATABASE_USER"] == "iam_user"
    assert probes[0].env["DATABASE_PASSWORD"] == "mounted-secret"
    assert probes[0].env["DATABASE_SCHEMA"] == "iam"
    assert probes[0].env["DOCUMENT_BUCKET"] == "iam-docs"
    assert probes[0].env["QDRANT_COLLECTION"] == "iam_memory"


def test_runtime_env_probes_collect_middleware_credentials_from_yaml() -> None:
    probes = runtime_env_probes(
        "test",
        None,
        namespace_resolver=lambda source_env, business_namespaces=None: ["test-base-public"],
        pod_reader=lambda namespace: {
            "items": [
                {
                    "metadata": {"name": "platform-0", "labels": {"app": "platform"}},
                    "spec": {
                        "containers": [
                            {
                                "name": "platform",
                                "envFrom": [{"configMapRef": {"name": "platform-config"}}],
                            }
                        ]
                    },
                }
            ]
        },
        secret_reader=lambda namespace, name: {},
        configmap_reader=lambda namespace, name: {
            "application.yml": """
spring:
  data:
    redis:
      password: redis-from-yaml
qdrant:
  service:
    api-key: qdrant-from-yaml
iotdb:
  url: iotdb://root:iotdb-from-yaml@iotdb:6667
redis:
  uri: redis://:redis-from-uri@redis:6379/0
"""
        },
    )

    assert probes[0].env["REDIS_PASSWORD"] == "redis-from-uri"
    assert probes[0].env["QDRANT_API_KEY"] == "qdrant-from-yaml"
    assert probes[0].env["IOTDB_USER"] == "root"
    assert probes[0].env["IOTDB_PASSWORD"] == "iotdb-from-yaml"


def test_runtime_env_probes_map_generic_secret_keys_by_source_name() -> None:
    def pod_reader(namespace: str) -> dict:
        return {
            "items": [
                {
                    "metadata": {"name": "middleware-client-0", "labels": {"app": "middleware-client"}},
                    "spec": {
                        "containers": [
                            {
                                "name": "middleware-client",
                                "envFrom": [
                                    {"secretRef": {"name": "redis-secret"}},
                                    {"secretRef": {"name": "qdrant-secret"}},
                                    {"secretRef": {"name": "iotdb-secret"}},
                                ],
                            }
                        ]
                    },
                }
            ]
        }

    secrets = {
        "redis-secret": {"password": "redis-generic-password"},
        "qdrant-secret": {"api-key": "qdrant-generic-key"},
        "iotdb-secret": {"password": "iotdb-generic-password"},
    }
    probes = runtime_env_probes(
        "test",
        None,
        namespace_resolver=lambda source_env, business_namespaces=None: ["test-base-public"],
        pod_reader=pod_reader,
        secret_reader=lambda namespace, name: secrets.get(name, {}),
        configmap_reader=lambda namespace, name: {},
    )

    assert probes[0].env["REDIS_PASSWORD"] == "redis-generic-password"
    assert probes[0].env["QDRANT_API_KEY"] == "qdrant-generic-key"
    assert probes[0].env["IOTDB_PASSWORD"] == "iotdb-generic-password"


def test_runtime_env_probes_collect_single_line_properties_and_subpath_mounts() -> None:
    def pod_reader(namespace: str) -> dict:
        return {
            "items": [
                {
                    "metadata": {"name": "eam-0", "labels": {"app": "eam"}},
                    "spec": {
                        "volumes": [
                            {
                                "name": "app-secret",
                                "secret": {
                                    "secretName": "eam-secret",
                                    "items": [{"key": "database-password", "path": "password.txt"}],
                                },
                            }
                        ],
                        "containers": [
                            {
                                "name": "eam",
                                "envFrom": [{"configMapRef": {"name": "eam-config"}}],
                                "volumeMounts": [{"name": "app-secret", "mountPath": "/run/password.txt", "subPath": "password.txt"}],
                            }
                        ],
                    },
                }
            ]
        }

    probes = runtime_env_probes(
        "test",
        None,
        namespace_resolver=lambda source_env, business_namespaces=None: ["test-biz-eam"],
        pod_reader=pod_reader,
        secret_reader=lambda namespace, name: {"database-password": "mounted-password", "other-password": "wrong"},
        configmap_reader=lambda namespace, name: {"application.properties": "spring.datasource.username=eam_user"},
    )

    assert probes[0].env["DATABASE_USER"] == "eam_user"
    assert probes[0].env["DATABASE_PASSWORD"] == "mounted-password"


def test_runtime_env_probes_ignores_unmatched_subpath_keys() -> None:
    probes = runtime_env_probes(
        "test",
        None,
        namespace_resolver=lambda source_env, business_namespaces=None: ["test-biz-eam"],
        pod_reader=lambda namespace: {
            "items": [
                {
                    "metadata": {"name": "eam-0", "labels": {"app": "eam"}},
                    "spec": {
                        "volumes": [
                            {
                                "name": "app-secret",
                                "secret": {
                                    "secretName": "eam-secret",
                                    "items": [{"key": "database-password", "path": "password.txt"}],
                                },
                            }
                        ],
                        "containers": [
                            {
                                "name": "eam",
                                "volumeMounts": [{"name": "app-secret", "mountPath": "/run/missing.txt", "subPath": "missing.txt"}],
                            }
                        ],
                    },
                }
            ]
        },
        secret_reader=lambda namespace, name: {"database-password": "should-not-leak"},
        configmap_reader=lambda namespace, name: {},
    )

    assert probes == []
