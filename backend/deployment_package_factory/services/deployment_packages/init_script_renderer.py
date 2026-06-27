from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from pathlib import PurePosixPath


PROJECT_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_OVERLAY_TEMPLATE_DIR = PROJECT_ROOT / "templates" / "overlays"


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


def render_init_files(manifest: dict, template_dir: Path | None = None) -> list[RenderedInitFile]:
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

    files.extend(_project_init_files(manifest, template_dir or DEFAULT_OVERLAY_TEMPLATE_DIR))
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
    lines.extend(
        [
            "",
            'PROJECT_INIT_DIR="${SCRIPT_DIR}/project"',
            'if [ -d "${PROJECT_INIT_DIR}" ] && { [ "${MODE}" = "all" ] || [ "${MODE}" = "database" ]; }; then',
            '  while IFS= read -r -d "" sql_file; do',
            '    dialect="$(basename "$(dirname "${sql_file}")")"',
            '    run_sql "${dialect}" "${sql_file}"',
            '  done < <(find "${PROJECT_INIT_DIR}" -type f \\( -path "*/postgres/*.sql" -o -path "*/dm/*.sql" \\) -print0 | sort -z)',
            "fi",
            "",
            'if [ -d "${PROJECT_INIT_DIR}" ] && { [ "${MODE}" = "all" ] || [ "${MODE}" = "middleware" ]; }; then',
            '  while IFS= read -r -d "" script_file; do',
            '    echo "Running project init script: ${script_file}"',
            '    "${script_file}"',
            '  done < <(find "${PROJECT_INIT_DIR}" -type f -name "*.sh" -print0 | sort -z)',
            "fi",
            "",
            'if [ -d "${PROJECT_INIT_DIR}" ] && { [ "${MODE}" = "all" ] || [ "${MODE}" = "middleware" ]; }; then',
            '  while IFS= read -r -d "" data_file; do',
            '    echo "Project init data asset: ${data_file}"',
            '  done < <(find "${PROJECT_INIT_DIR}" -type f \\( -name "*.json" -o -name "*.bpmn" -o -name "*.bpmn20.xml" -o -name "*.txt" \\) -print0 | sort -z)',
            "fi",
        ]
    )
    lines.append('echo "Init script dispatch completed."')
    return "\n".join(lines) + "\n"


def _init_readme(manifest: dict) -> str:
    middleware = ", ".join(manifest["middleware"]) or "-"
    return (
        "# 初始化脚本\n\n"
        f"数据库：`{manifest['database']}`\n\n"
        f"中间件：{middleware}\n\n"
        "`run-init.sh` 是统一入口。脚本默认保持幂等设计，当前生成的是生产实施可补全的安全占位模板。\n\n"
        "项目级初始化资产会从 `templates/overlays/<project>/init/` 合并到 `init/project/<project>/`，并由统一入口按 database/middleware 模式调度。\n"
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


def _project_init_files(manifest: dict, template_dir: Path) -> list[RenderedInitFile]:
    project_key = manifest.get("projectKey")
    if not project_key:
        return []
    project_init_dir = (template_dir / project_key / "init").resolve()
    template_root = template_dir.resolve()
    if not project_init_dir.exists():
        return []
    if not project_init_dir.is_dir():
        raise ValueError(f"Project init template path must be a directory: {project_init_dir}")
    if not project_init_dir.is_relative_to(template_root):
        raise ValueError(f"Project init template path escapes template root: {project_init_dir}")

    files: list[RenderedInitFile] = []
    for path in sorted(item for item in project_init_dir.rglob("*") if item.is_file()):
        relative = path.relative_to(project_init_dir).as_posix()
        if _has_unsafe_path_segment(relative):
            raise ValueError(f"Unsafe project init template path: {relative}")
        files.append(
            RenderedInitFile(
                PurePosixPath("init") / "project" / project_key / PurePosixPath(relative),
                path.read_text(encoding="utf-8"),
                executable=path.suffix == ".sh",
            )
        )
    return files


def _has_unsafe_path_segment(path: str) -> bool:
    return any(segment in {"", ".", ".."} for segment in PurePosixPath(path).parts)
