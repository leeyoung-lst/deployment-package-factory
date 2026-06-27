from __future__ import annotations

from deployment_package_factory.services.deployment_packages.init_script_renderer import render_init_files


def test_render_init_files_selects_database_and_middleware_scripts() -> None:
    files = render_init_files(_manifest())
    by_path = {item.path.as_posix(): item for item in files}

    assert "init/run-init.sh" in by_path
    assert "init/README.md" in by_path
    assert "init/postgres/001_schema.sql" in by_path
    assert "init/dm/001_schema.sql" not in by_path
    assert "init/minio/create-buckets.sh" in by_path
    assert "init/qdrant/create-collections.sh" in by_path
    assert "init/camunda/bootstrap-admin.sh" in by_path
    assert by_path["init/run-init.sh"].executable
    assert by_path["init/minio/create-buckets.sh"].executable
    assert not by_path["init/postgres/001_schema.sql"].executable


def test_render_init_files_contains_idempotent_placeholders() -> None:
    files = render_init_files(_manifest())
    by_path = {item.path.as_posix(): item.content for item in files}

    assert "CREATE SCHEMA IF NOT EXISTS local_ai_platform" in by_path["init/postgres/001_schema.sql"]
    assert "mc mb --ignore-existing" in by_path["init/minio/create-buckets.sh"]
    assert "PUT \"${QDRANT_URL}/collections/agent_memory\"" in by_path["init/qdrant/create-collections.sh"]
    assert "Bootstrap Camunda tenants" in by_path["init/camunda/bootstrap-admin.sh"]
    assert "run_sql \"postgres\"" in by_path["init/run-init.sh"]
    assert "PROJECT_INIT_DIR" in by_path["init/run-init.sh"]


def test_render_init_files_merges_project_init_templates(tmp_path) -> None:
    project_dir = tmp_path / "mes-lite" / "init"
    (project_dir / "dm").mkdir(parents=True)
    (project_dir / "minio").mkdir()
    (project_dir / "qdrant").mkdir()
    (project_dir / "dm" / "010_project.sql").write_text("-- project sql\n", encoding="utf-8")
    (project_dir / "minio" / "bootstrap.sh").write_text("#!/usr/bin/env bash\necho minio\n", encoding="utf-8")
    (project_dir / "qdrant" / "collections.json").write_text("{}\n", encoding="utf-8")

    files = render_init_files(_project_manifest(), template_dir=tmp_path)
    by_path = {item.path.as_posix(): item for item in files}

    assert by_path["init/project/mes-lite/dm/010_project.sql"].content == "-- project sql\n"
    assert by_path["init/project/mes-lite/minio/bootstrap.sh"].executable is True
    assert by_path["init/project/mes-lite/qdrant/collections.json"].content == "{}\n"
    assert 'find "${PROJECT_INIT_DIR}" -type f \\( -path "*/postgres/*.sql" -o -path "*/dm/*.sql" \\)' in by_path["init/run-init.sh"].content


def test_default_project_init_templates_are_merged_for_mes_lite() -> None:
    files = render_init_files(_project_manifest())
    paths = {item.path.as_posix() for item in files}

    assert "init/project/mes-lite/dm/010_mes_lite_schema.sql" in paths
    assert "init/project/mes-lite/qdrant/collections.json" in paths


def _manifest() -> dict:
    return {
        "packageId": "pkg-test",
        "database": "postgres",
        "platformServices": ["iam", "ai-agent", "workflow-camunda"],
        "businessServices": ["eam"],
        "middleware": ["postgres", "redis", "minio", "qdrant", "camunda"],
    }


def _project_manifest() -> dict:
    return {
        "packageId": "pkg-test",
        "projectKey": "mes-lite",
        "database": "dm",
        "platformServices": ["iam"],
        "businessServices": ["mes"],
        "middleware": ["dm", "redis", "qdrant"],
    }
