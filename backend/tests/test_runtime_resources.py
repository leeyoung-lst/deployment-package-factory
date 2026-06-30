from __future__ import annotations

from deployment_package_factory.services.deployment_packages.catalog import load_catalog
from deployment_package_factory.services.deployment_packages.dependency_resolver import resolve_package_preview
from deployment_package_factory.services.deployment_packages.models import BusinessSelection, PackageBuildRequest
from deployment_package_factory.services.deployment_packages.runtime_resources import RuntimeEnvProbe, build_runtime_config, runtime_env_from_config


def test_runtime_resources_dedupe_shared_database_bucket_and_collection() -> None:
    request = PackageBuildRequest(
        sourceEnv="test",
        platformServices=["iam", "ai-agent"],
        businessServices=[BusinessSelection(name="eam", profile="4x60")],
        database="postgres",
    )
    catalog = load_catalog()
    preview = resolve_package_preview(request, catalog)
    middleware_config = {"postgres": catalog.database_options["postgres"].model_dump(by_alias=True)}
    config = build_runtime_config(
        request=request,
        preview=preview,
        middleware_config=middleware_config,
        runtime_env={"DATABASE_USER": "shared_user", "DATABASE_PASSWORD": "shared-password"},
        probes=[
            RuntimeEnvProbe("iam", "IAM", {"DATABASE_URL": "postgresql://shared:pw@postgres:5432/local_ai?currentSchema=platform"}),
            RuntimeEnvProbe("eam", "EAM", {"DATABASE_URL": "postgresql://shared:pw@postgres:5432/local_ai?currentSchema=platform", "MINIO_BUCKET": "docs"}),
            RuntimeEnvProbe("ai-agent", "AI Agent", {"DATABASE_URL": "postgresql://agent:pw@postgres:5432/ai_agent?currentSchema=agent", "QDRANT_COLLECTION": "agent_memory"}),
            RuntimeEnvProbe("file-documents", "Documents", {"MINIO_BUCKET": "docs"}),
        ],
    )

    databases = [item for item in config["resources"] if item["type"] == "databaseSchema"]
    buckets = [item for item in config["resources"] if item["type"] == "bucket" and item["name"] == "docs"]
    collections = [item for item in config["resources"] if item["type"] == "collection" and item["name"] == "agent_memory"]

    assert len([item for item in databases if item["name"] == "postgres local_ai.platform"]) == 1
    assert next(item for item in databases if item["name"] == "postgres local_ai.platform")["usedBy"] == ["iam", "eam"]
    assert next(item for item in databases if item["name"] == "postgres ai_agent.agent")["usedBy"] == ["ai-agent"]
    assert buckets[0]["usedBy"] == ["eam", "file-documents"]
    assert collections[0]["usedBy"] == ["ai-agent"]


def test_runtime_config_overrides_feed_env_values() -> None:
    request = PackageBuildRequest(
        sourceEnv="test",
        businessServices=[BusinessSelection(name="eam", profile="4x60")],
        database="postgres",
        runtimeConfigOverrides={"DATABASE_NAME": "eam_prod", "DATABASE_USER": "eam_user", "DATABASE_PASSWORD": "prod-password"},
    )
    catalog = load_catalog()
    preview = resolve_package_preview(request, catalog)
    middleware_config = {"postgres": catalog.database_options["postgres"].model_dump(by_alias=True)}
    config = build_runtime_config(
        request=request,
        preview=preview,
        middleware_config=middleware_config,
        runtime_env={},
    )

    env_values = runtime_env_from_config(config)

    assert env_values["DATABASE_NAME"] == "eam_prod"
    assert env_values["DATABASE_USER"] == "eam_user"
    assert env_values["DATABASE_PASSWORD"] == "prod-password"


def test_database_resource_overrides_are_scoped_per_resource() -> None:
    request = PackageBuildRequest(
        sourceEnv="test",
        businessServices=[BusinessSelection(name="eam", profile="4x60")],
        database="postgres",
        runtimeConfigOverrides={
            "databaseschema-postgres-local-ai-public.databaseName": "eam_prod",
            "databaseschema-postgres-local-ai-public.schema": "eam_schema",
            "databaseschema-postgres-local-ai-public.username": "eam_user",
            "databaseschema-postgres-local-ai-public.password": "prod-password",
        },
    )
    catalog = load_catalog()
    preview = resolve_package_preview(request, catalog)
    config = build_runtime_config(
        request=request,
        preview=preview,
        middleware_config={"postgres": catalog.database_options["postgres"].model_dump(by_alias=True)},
        runtime_env={},
    )

    database = next(item for item in config["resources"] if item["type"] == "databaseSchema")
    values = {item["name"]: item["value"] for item in database["items"]}
    env_values = runtime_env_from_config(config)

    assert database["name"] == "postgres eam_prod.eam_schema"
    assert values["username"] == "eam_user"
    assert values["password"] == "prod-password"
    assert env_values["DATABASE_NAME"] == "local_ai"
    assert env_values["DATABASE_PASSWORD"] == "__REPLACE_WITH_DATABASE_PASSWORD__"


def test_runtime_resource_item_overrides_are_scoped_by_resource_key() -> None:
    request = PackageBuildRequest(
        sourceEnv="test",
        platformServices=["file-documents"],
        businessServices=[BusinessSelection(name="eam", profile="4x60")],
        database="postgres",
        runtimeConfigOverrides={"bucket-minio-docs.bucket": "eam-docs-prod"},
    )
    catalog = load_catalog()
    preview = resolve_package_preview(request, catalog)
    middleware_config = {"minio": catalog.middleware["minio"].model_dump(by_alias=True)}
    config = build_runtime_config(
        request=request,
        preview=preview,
        middleware_config=middleware_config,
        runtime_env={},
        probes=[
            RuntimeEnvProbe("eam", "EAM", {"MINIO_BUCKET": "docs"}),
            RuntimeEnvProbe("file-documents", "Documents", {"MINIO_BUCKET": "docs"}),
        ],
    )

    buckets = [item for item in config["resources"] if item["type"] == "bucket"]

    assert len(buckets) == 1
    assert buckets[0]["name"] == "eam-docs-prod"
    assert buckets[0]["usedBy"] == ["eam", "file-documents"]


def test_database_resource_uses_jdbc_url_and_probe_credentials() -> None:
    request = PackageBuildRequest(sourceEnv="test", platformServices=["iam"], database="postgres")
    catalog = load_catalog()
    preview = resolve_package_preview(request, catalog)
    config = build_runtime_config(
        request=request,
        preview=preview,
        middleware_config={"postgres": catalog.database_options["postgres"].model_dump(by_alias=True)},
        runtime_env={},
        probes=[
            RuntimeEnvProbe(
                "iam",
                "IAM",
                {
                    "DATABASE_URL": "jdbc:postgresql://postgres:5432/local_ai?currentSchema=iam",
                    "DATABASE_USER": "iam_user",
                    "DATABASE_PASSWORD": "iam_password",
                },
            )
        ],
    )

    database = next(item for item in config["resources"] if item["type"] == "databaseSchema")
    values = {item["name"]: item["value"] for item in database["items"]}

    assert database["name"] == "postgres local_ai.iam"
    assert values["username"] == "iam_user"
    assert values["password"] == "iam_password"
