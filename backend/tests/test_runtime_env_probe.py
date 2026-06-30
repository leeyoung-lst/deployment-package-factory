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
