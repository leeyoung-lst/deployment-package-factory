from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath


DATABASE_INIT_PATHS = {
    "postgres": "init/postgres/001_schema.sql",
    "dm": "init/dm/001_schema.sql",
}
MIDDLEWARE_INIT_PATHS = {
    "minio": "init/minio/create-buckets.sh",
    "qdrant": "init/qdrant/create-collections.sh",
    "camunda": "init/camunda/bootstrap-admin.sh",
}


@dataclass(frozen=True)
class RenderedInitFile:
    path: PurePosixPath
    content: str
    executable: bool = False


def render_init_files(manifest: dict) -> list[RenderedInitFile]:
    files = [
        RenderedInitFile(PurePosixPath("init/run-init.sh"), _run_init_script(manifest), executable=True),
        RenderedInitFile(PurePosixPath("init/README.md"), _init_readme(manifest)),
    ]

    database = manifest["database"]
    if database == "postgres":
        files.append(RenderedInitFile(PurePosixPath(DATABASE_INIT_PATHS["postgres"]), _postgres_schema_sql(manifest)))
    elif database == "dm":
        files.append(RenderedInitFile(PurePosixPath(DATABASE_INIT_PATHS["dm"]), _dm_schema_sql(manifest)))

    middleware = set(manifest["middleware"])
    if "minio" in middleware:
        files.append(RenderedInitFile(PurePosixPath(MIDDLEWARE_INIT_PATHS["minio"]), _minio_init_script(manifest), executable=True))
    if "qdrant" in middleware:
        files.append(RenderedInitFile(PurePosixPath(MIDDLEWARE_INIT_PATHS["qdrant"]), _qdrant_init_script(manifest), executable=True))
    if "camunda" in middleware:
        files.append(RenderedInitFile(PurePosixPath(MIDDLEWARE_INIT_PATHS["camunda"]), _camunda_init_script(manifest), executable=True))

    return files


def _run_init_script(manifest: dict) -> str:
    database = manifest["database"]
    middleware = set(manifest["middleware"])
    lines = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        'SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"',
        'MODE="${1:-all}"',
        "",
        "run_sql() {",
        '  local dialect="$1"',
        '  local file="$2"',
        '  echo "Preparing ${dialect} init script: ${file}"',
        '  echo "Apply this SQL with your production database client after secrets are configured."',
        "}",
        "",
        "case \"${MODE}\" in",
        "  all|database)",
    ]
    if database in DATABASE_INIT_PATHS:
        lines.append(f'    run_sql "{database}" "${{SCRIPT_DIR}}/{DATABASE_INIT_PATHS[database].split("/", 1)[1]}"')
    else:
        lines.append('    echo "No database init script selected."')
    lines.extend(
        [
            "    ;;",
            "  middleware)",
            "    ;;",
            "  *)",
            '    echo "Unknown init mode: ${MODE}" >&2',
            "    exit 1",
            "    ;;",
            "esac",
            "",
        ]
    )

    if "minio" in middleware:
        lines.append('if [ "${MODE}" = "all" ] || [ "${MODE}" = "middleware" ]; then')
        lines.append('  "${SCRIPT_DIR}/minio/create-buckets.sh"')
        lines.append("fi")
    if "qdrant" in middleware:
        lines.append('if [ "${MODE}" = "all" ] || [ "${MODE}" = "middleware" ]; then')
        lines.append('  "${SCRIPT_DIR}/qdrant/create-collections.sh"')
        lines.append("fi")
    if "camunda" in middleware:
        lines.append('if [ "${MODE}" = "all" ] || [ "${MODE}" = "middleware" ]; then')
        lines.append('  "${SCRIPT_DIR}/camunda/bootstrap-admin.sh"')
        lines.append("fi")
    lines.append('echo "Init script dispatch completed."')
    return "\n".join(lines) + "\n"


def _init_readme(manifest: dict) -> str:
    middleware = ", ".join(manifest["middleware"]) or "-"
    return (
        "# 初始化脚本\n\n"
        f"数据库：`{manifest['database']}`\n\n"
        f"中间件：{middleware}\n\n"
        "`run-init.sh` 是统一入口。脚本默认保持幂等设计，当前生成的是生产实施可补全的安全占位模板。\n"
    )


def _postgres_schema_sql(manifest: dict) -> str:
    services = "\n".join(f"-- service: {item}" for item in manifest["platformServices"] + manifest["businessServices"])
    return (
        "-- PostgreSQL schema initialization placeholder.\n"
        "-- Idempotent production SQL should use CREATE IF NOT EXISTS and upsert semantics.\n"
        f"{services}\n"
        "CREATE SCHEMA IF NOT EXISTS local_ai_platform;\n"
    )


def _dm_schema_sql(manifest: dict) -> str:
    services = "\n".join(f"-- service: {item}" for item in manifest["platformServices"] + manifest["businessServices"])
    return (
        "-- DM schema initialization placeholder.\n"
        "-- Idempotent production SQL should guard existing users, schemas, and seed rows.\n"
        f"{services}\n"
        "-- TODO: create DM schema with production account and tablespace policy.\n"
    )


def _minio_init_script(manifest: dict) -> str:
    buckets = sorted(set(manifest["businessServices"]) | {"platform-documents"})
    lines = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        'MINIO_ALIAS="${MINIO_ALIAS:-local-ai}"',
        'if ! command -v mc >/dev/null 2>&1; then',
        '  echo "MinIO client mc is not available; print bucket initialization commands only."',
        "  DRY_RUN=1",
        "else",
        "  DRY_RUN=0",
        "fi",
        "",
    ]
    for bucket in buckets:
        lines.append(f'if [ "${{DRY_RUN}}" = "1" ]; then echo "mc mb --ignore-existing ${{MINIO_ALIAS}}/{bucket}"; else mc mb --ignore-existing "${{MINIO_ALIAS}}/{bucket}"; fi')
    return "\n".join(lines) + "\n"


def _qdrant_init_script(manifest: dict) -> str:
    collections = sorted({"agent_memory", *(f"{item}_knowledge" for item in manifest["businessServices"])})
    lines = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        'QDRANT_URL="${QDRANT_URL:-http://qdrant:6333}"',
        'if ! command -v curl >/dev/null 2>&1; then',
        '  echo "curl is not available; skip Qdrant collection initialization."',
        "  exit 0",
        "fi",
        "",
    ]
    for collection in collections:
        lines.extend(
            [
                f'curl -fsS -X PUT "${{QDRANT_URL}}/collections/{collection}" \\',
                "  -H 'Content-Type: application/json' \\",
                "  -d '{\"vectors\":{\"size\":1536,\"distance\":\"Cosine\"}}'",
            ]
        )
    return "\n".join(lines) + "\n"


def _camunda_init_script(manifest: dict) -> str:
    return (
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        'CAMUNDA_URL="${CAMUNDA_URL:-http://camunda:8080}"\n'
        f'echo "Bootstrap Camunda tenants and admin groups for {manifest["packageId"]} at ${{CAMUNDA_URL}}."\n'
        "echo \"TODO: import BPMN models and seed operator groups with Camunda REST API.\"\n"
    )
