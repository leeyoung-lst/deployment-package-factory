from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from pathlib import PurePosixPath

from deployment_package_factory.services.deployment_packages.template_paths import default_overlay_template_dir
from deployment_package_factory.services.deployment_packages.init_data_generators import (
    generate_default_iam_data,
    generate_gateway_default_data,
    generate_monitoring_tables,
    generate_workflow_tables,
    generate_document_tables,
    generate_notification_tables,
    generate_cache_tables,
    generate_job_queue_tables,
)


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

    files.extend(_project_init_files(manifest, template_dir or default_overlay_template_dir()))
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
    resources = _resources_by_type(manifest, "databaseSchema")
    services = "\n".join(f"-- service: {item}" for item in manifest["platformServices"] + manifest["businessServices"])
    platform_services = set(manifest["platformServices"])
    business_services = set(manifest["businessServices"])

    # 收集所有 schema
    schema_lines = [
        f"CREATE SCHEMA IF NOT EXISTS {_sql_ident(_resource_value(resource, 'schema', 'public'))};"
        for resource in resources
        if (resource.get("middlewareKey") or manifest.get("database")) == "postgres"
    ]
    if not schema_lines:
        schema_lines = ["CREATE SCHEMA IF NOT EXISTS local_ai_platform;"]

    # 生成核心平台表结构
    core_tables = []

    # IAM 核心表
    if "iam" in platform_services:
        core_tables.extend([
            "",
            "-- IAM Core Tables",
            "CREATE SCHEMA IF NOT EXISTS iam;",
            "",
            "CREATE TABLE IF NOT EXISTS iam.users (",
            "  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),",
            "  username VARCHAR(255) UNIQUE NOT NULL,",
            "  email VARCHAR(255),",
            "  password_hash VARCHAR(255) NOT NULL,",
            "  display_name VARCHAR(255),",
            "  is_active BOOLEAN DEFAULT TRUE,",
            "  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,",
            "  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
            ");",
            "",
            "CREATE TABLE IF NOT EXISTS iam.roles (",
            "  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),",
            "  name VARCHAR(255) UNIQUE NOT NULL,",
            "  description TEXT,",
            "  permissions JSONB DEFAULT '[]'::JSONB,",
            "  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,",
            "  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
            ");",
            "",
            "CREATE TABLE IF NOT EXISTS iam.user_roles (",
            "  user_id UUID NOT NULL REFERENCES iam.users(id) ON DELETE CASCADE,",
            "  role_id UUID NOT NULL REFERENCES iam.roles(id) ON DELETE CASCADE,",
            "  assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,",
            "  PRIMARY KEY (user_id, role_id)",
            ");",
            "",
            "CREATE INDEX IF NOT EXISTS idx_users_username ON iam.users(username);",
            "CREATE INDEX IF NOT EXISTS idx_user_roles_user_id ON iam.user_roles(user_id);",
        ])

    # Audit 核心表
    if "audit" in platform_services:
        core_tables.extend([
            "",
            "-- Audit Core Tables",
            "CREATE SCHEMA IF NOT EXISTS audit;",
            "",
            "CREATE TABLE IF NOT EXISTS audit.events (",
            "  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),",
            "  action VARCHAR(255) NOT NULL,",
            "  operator VARCHAR(255),",
            "  client_ip VARCHAR(45),",
            "  target_id VARCHAR(255),",
            "  status VARCHAR(50),",
            "  message TEXT,",
            "  metadata JSONB DEFAULT '{}'::JSONB,",
            "  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
            ");",
            "",
            "CREATE INDEX IF NOT EXISTS idx_audit_events_action ON audit.events(action);",
            "CREATE INDEX IF NOT EXISTS idx_audit_events_operator ON audit.events(operator);",
            "CREATE INDEX IF NOT EXISTS idx_audit_events_created_at ON audit.events(created_at DESC);",
        ])

    # 业务服务 schema（仅创建 schema，具体表结构由项目级 SQL 补充）
    for service in sorted(business_services):
        if service in ["eam", "mes", "erp", "aps"]:
            core_tables.extend([
                "",
                f"-- {service.upper()} Business Schema",
                f"CREATE SCHEMA IF NOT EXISTS {_sql_ident(f'{service}_schema')};",
            ])

    # 添加增强的表结构
    enhanced_tables = []

    # 监控表
    enhanced_tables.append(generate_monitoring_tables())

    # 工作流表
    enhanced_tables.append(generate_workflow_tables())

    # 文档管理表
    enhanced_tables.append(generate_document_tables())

    # 通知系统表
    enhanced_tables.append(generate_notification_tables())

    # 缓存辅助表
    enhanced_tables.append(generate_cache_tables())

    # 任务队列表
    enhanced_tables.append(generate_job_queue_tables())

    # 添加默认数据
    default_data = []

    # IAM 默认数据
    if "iam" in platform_services:
        default_data.append(generate_default_iam_data())

    # Gateway 默认数据
    if "api-gateway" in platform_services or "gateway" in platform_services:
        default_data.append(generate_gateway_default_data())

    return (
        "-- PostgreSQL schema and core table initialization.\n"
        "-- This script is idempotent and can be executed multiple times.\n"
        f"{services}\n"
        "\n"
        + "\n".join(dict.fromkeys(schema_lines))
        + "\n"
        + "\n".join(core_tables)
        + "\n"
        + "\n".join(enhanced_tables)
        + "\n"
        + "\n".join(default_data)
        + "\n"
    )


def _dm_schema_sql(manifest: dict) -> str:
    services = "\n".join(f"-- service: {item}" for item in manifest["platformServices"] + manifest["businessServices"])
    resources = _resources_by_type(manifest, "databaseSchema")
    platform_services = set(manifest["platformServices"])
    business_services = set(manifest["businessServices"])

    schema_lines = [
        f"-- DM schema resource: {_resource_value(resource, 'databaseName', 'LOCAL_AI')}.{_resource_value(resource, 'schema', 'PUBLIC')}"
        for resource in resources
        if (resource.get("middlewareKey") or manifest.get("database")) == "dm"
    ]

    # 生成达梦核心表结构（使用达梦 SQL 语法）
    core_tables = []

    # IAM 核心表（达梦语法）
    if "iam" in platform_services:
        core_tables.extend([
            "",
            "-- IAM Core Tables (DM Syntax)",
            "-- Note: Adjust tablespace and storage parameters for production",
            "",
            "CREATE TABLE IAM_USERS (",
            "  ID VARCHAR2(36) PRIMARY KEY,",
            "  USERNAME VARCHAR2(255) UNIQUE NOT NULL,",
            "  EMAIL VARCHAR2(255),",
            "  PASSWORD_HASH VARCHAR2(255) NOT NULL,",
            "  DISPLAY_NAME VARCHAR2(255),",
            "  IS_ACTIVE NUMBER(1) DEFAULT 1,",
            "  CREATED_AT TIMESTAMP DEFAULT SYSDATE,",
            "  UPDATED_AT TIMESTAMP DEFAULT SYSDATE",
            ");",
            "",
            "CREATE TABLE IAM_ROLES (",
            "  ID VARCHAR2(36) PRIMARY KEY,",
            "  NAME VARCHAR2(255) UNIQUE NOT NULL,",
            "  DESCRIPTION CLOB,",
            "  PERMISSIONS CLOB,",
            "  CREATED_AT TIMESTAMP DEFAULT SYSDATE,",
            "  UPDATED_AT TIMESTAMP DEFAULT SYSDATE",
            ");",
            "",
            "CREATE TABLE IAM_USER_ROLES (",
            "  USER_ID VARCHAR2(36) NOT NULL,",
            "  ROLE_ID VARCHAR2(36) NOT NULL,",
            "  ASSIGNED_AT TIMESTAMP DEFAULT SYSDATE,",
            "  PRIMARY KEY (USER_ID, ROLE_ID)",
            ");",
            "",
            "CREATE INDEX IDX_USERS_USERNAME ON IAM_USERS(USERNAME);",
            "CREATE INDEX IDX_USER_ROLES_USER_ID ON IAM_USER_ROLES(USER_ID);",
        ])

    # Audit 核心表（达梦语法）
    if "audit" in platform_services:
        core_tables.extend([
            "",
            "-- Audit Core Tables (DM Syntax)",
            "",
            "CREATE TABLE AUDIT_EVENTS (",
            "  ID VARCHAR2(36) PRIMARY KEY,",
            "  ACTION VARCHAR2(255) NOT NULL,",
            "  OPERATOR VARCHAR2(255),",
            "  CLIENT_IP VARCHAR2(45),",
            "  TARGET_ID VARCHAR2(255),",
            "  STATUS VARCHAR2(50),",
            "  MESSAGE CLOB,",
            "  METADATA CLOB,",
            "  CREATED_AT TIMESTAMP DEFAULT SYSDATE",
            ");",
            "",
            "CREATE INDEX IDX_AUDIT_EVENTS_ACTION ON AUDIT_EVENTS(ACTION);",
            "CREATE INDEX IDX_AUDIT_EVENTS_OPERATOR ON AUDIT_EVENTS(OPERATOR);",
            "CREATE INDEX IDX_AUDIT_EVENTS_CREATED_AT ON AUDIT_EVENTS(CREATED_AT DESC);",
        ])

    # 业务服务 schema 注释（达梦需要在 DBA 权限下创建 schema/用户）
    for service in sorted(business_services):
        if service in ["eam", "mes", "erp", "aps"]:
            core_tables.extend([
                "",
                f"-- {service.upper()} Business Schema",
                f"-- Production: CREATE USER {service.upper()}_SCHEMA IDENTIFIED BY <password>;",
                f"-- Production: GRANT CONNECT, RESOURCE TO {service.upper()}_SCHEMA;",
            ])

    return (
        "-- DM schema and core table initialization.\n"
        "-- This script uses DM-specific syntax (VARCHAR2, SYSDATE, CLOB).\n"
        "-- Production deployment should be executed by DBA with appropriate tablespace configuration.\n"
        f"{services}\n"
        + ("\n".join(dict.fromkeys(schema_lines)) + "\n" if schema_lines else "")
        + "\n".join(core_tables)
        + "\n"
    )


def _minio_init_script(manifest: dict) -> str:
    buckets = [
        _resource_value(resource, "bucket", resource.get("name", ""))
        for resource in _resources_by_type(manifest, "bucket")
    ]
    if not buckets:
        buckets = sorted(set(manifest["businessServices"]) | {"platform-documents"})
    lines = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        'SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"',
        'PROJECT_INIT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)/project"',
        'MINIO_ALIAS="${MINIO_ALIAS:-local-ai}"',
        'if ! command -v mc >/dev/null 2>&1; then',
        '  echo "MinIO client mc is not available; print bucket initialization commands only."',
        "  DRY_RUN=1",
        "else",
        "  DRY_RUN=0",
        "fi",
        "",
        "create_bucket() {",
        '  local bucket="$1"',
        '  if [ -z "${bucket}" ] || [[ "${bucket}" = \\#* ]]; then',
        "    return 0",
        "  fi",
        '  if [ "${DRY_RUN}" = "1" ]; then',
        '    echo "mc mb --ignore-existing ${MINIO_ALIAS}/${bucket}"',
        "  else",
        '    mc mb --ignore-existing "${MINIO_ALIAS}/${bucket}"',
        "  fi",
        "}",
        "",
    ]
    for bucket in sorted(dict.fromkeys(item for item in buckets if item)):
        lines.append(f'create_bucket "{bucket}"')
    lines.extend(
        [
            "",
            'if [ -d "${PROJECT_INIT_DIR}" ]; then',
            '  while IFS= read -r -d "" bucket_file; do',
            '    echo "Reading project MinIO buckets: ${bucket_file}"',
            '    while IFS= read -r bucket || [ -n "${bucket}" ]; do',
            '      bucket="$(printf "%s" "${bucket}" | sed "s/^[[:space:]]*//;s/[[:space:]]*$//")"',
            '      create_bucket "${bucket}"',
            '    done < "${bucket_file}"',
            '  done < <(find "${PROJECT_INIT_DIR}" -type f -path "*/minio/buckets.txt" -print0 | sort -z)',
            "fi",
        ]
    )
    return "\n".join(lines) + "\n"


def _qdrant_init_script(manifest: dict) -> str:
    collection_specs = [
        (
            _resource_value(resource, "collection", resource.get("name", "")),
            _resource_value(resource, "vectorSize", "1536"),
            _resource_value(resource, "distance", "Cosine"),
        )
        for resource in _resources_by_type(manifest, "collection")
    ]
    if not collection_specs:
        collection_specs = [(item, "1536", "Cosine") for item in sorted({"agent_memory", *(f"{item}_knowledge" for item in manifest["businessServices"])})]
    lines = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        'SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"',
        'PROJECT_INIT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)/project"',
        'QDRANT_URL="${QDRANT_URL:-http://qdrant:6333}"',
        'if ! command -v curl >/dev/null 2>&1; then',
        '  echo "curl is not available; skip Qdrant collection initialization."',
        "  exit 0",
        "fi",
        "",
        "create_collection() {",
        '  local name="$1"',
        '  local size="${2:-1536}"',
        '  local distance="${3:-Cosine}"',
        '  curl -fsS -X PUT "${QDRANT_URL}/collections/${name}" \\',
        "    -H 'Content-Type: application/json' \\",
        '    -d "{\\"vectors\\":{\\"size\\":${size},\\"distance\\":\\"${distance}\\"}}"',
        "}",
        "",
    ]
    for collection, size, distance in sorted(dict.fromkeys(collection_specs)):
        if collection:
            lines.append(f'create_collection "{collection}" "{size}" "{distance}"')
    lines.extend(
        [
            "",
            'if [ -d "${PROJECT_INIT_DIR}" ]; then',
            '  while IFS= read -r -d "" collections_file; do',
            '    echo "Reading project Qdrant collections: ${collections_file}"',
            '    if command -v python3 >/dev/null 2>&1; then',
            '      python3 - "${collections_file}" <<\'PY\' | while IFS= read -r spec; do',
            "import json",
            "import sys",
            "from pathlib import Path",
            "payload = json.loads(Path(sys.argv[1]).read_text(encoding=\"utf-8\"))",
            "for item in payload.get(\"collections\", []):",
            "    print(\"\\t\".join([str(item.get(\"name\", \"\")), str(item.get(\"vectorSize\", 1536)), str(item.get(\"distance\", \"Cosine\"))]))",
            "PY",
            '        IFS="$(printf \'\\t\')" read -r name size distance <<EOF',
            "${spec}",
            "EOF",
            '        [ -n "${name}" ] && create_collection "${name}" "${size}" "${distance}"',
            "      done",
            "    else",
            '      echo "python3 is not available; project Qdrant asset pending: ${collections_file}"',
            "    fi",
            '  done < <(find "${PROJECT_INIT_DIR}" -type f -path "*/qdrant/collections.json" -print0 | sort -z)',
            "fi",
        ]
    )
    return "\n".join(lines) + "\n"


def _camunda_init_script(manifest: dict) -> str:
    return (
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        'SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"\n'
        'PROJECT_INIT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)/project"\n'
        'CAMUNDA_URL="${CAMUNDA_URL:-http://camunda:8080}"\n'
        'CAMUNDA_ENGINE_URL="${CAMUNDA_URL}/engine-rest"\n'
        'CAMUNDA_ADMIN_USER="${CAMUNDA_ADMIN_USER:-admin}"\n'
        'CAMUNDA_ADMIN_PASSWORD="${CAMUNDA_ADMIN_PASSWORD:-admin}"\n'
        "\n"
        f'echo "Bootstrapping Camunda for {manifest["packageId"]} at ${{CAMUNDA_URL}}"\n'
        "\n"
        "# Check Camunda availability\n"
        "check_camunda_ready() {\n"
        '  if ! command -v curl >/dev/null 2>&1; then\n'
        '    echo "curl is not available; cannot verify Camunda readiness."\n'
        "    return 1\n"
        "  fi\n"
        '  if curl -fsS -u "${CAMUNDA_ADMIN_USER}:${CAMUNDA_ADMIN_PASSWORD}" \\\n'
        '    "${CAMUNDA_ENGINE_URL}/version" >/dev/null 2>&1; then\n'
        '    echo "Camunda is ready at ${CAMUNDA_ENGINE_URL}"\n'
        "    return 0\n"
        "  else\n"
        '    echo "Warning: Camunda is not accessible at ${CAMUNDA_ENGINE_URL}"\n'
        '    echo "Check CAMUNDA_URL, CAMUNDA_ADMIN_USER, and CAMUNDA_ADMIN_PASSWORD."\n'
        "    return 1\n"
        "  fi\n"
        "}\n"
        "\n"
        "# Deploy BPMN/DMN process model\n"
        "deploy_process_model() {\n"
        '  local model_file="$1"\n'
        '  local deployment_name="$(basename "${model_file}")"\n'
        '  if ! command -v curl >/dev/null 2>&1; then\n'
        '    echo "curl is not available; pending Camunda deployment: ${model_file}"\n'
        "    return 0\n"
        "  fi\n"
        '  echo "Deploying Camunda model: ${model_file}"\n'
        '  if curl -fsS -u "${CAMUNDA_ADMIN_USER}:${CAMUNDA_ADMIN_PASSWORD}" \\\n'
        '    -X POST "${CAMUNDA_ENGINE_URL}/deployment/create" \\\n'
        '    -F "deployment-name=${deployment_name}" \\\n'
        '    -F "enable-duplicate-filtering=true" \\\n'
        '    -F "deploy-changed-only=true" \\\n'
        '    -F "data=@${model_file}"; then\n'
        '    echo "Successfully deployed: ${deployment_name}"\n'
        "  else\n"
        '    echo "Warning: Failed to deploy ${deployment_name}"\n'
        "  fi\n"
        "}\n"
        "\n"
        "# Check Camunda readiness\n"
        "check_camunda_ready || exit 0\n"
        "\n"
        "# Deploy project-level BPMN/DMN models\n"
        'if [ -d "${PROJECT_INIT_DIR}" ]; then\n'
        '  while IFS= read -r -d "" model_file; do\n'
        '    deploy_process_model "${model_file}"\n'
        '  done < <(find "${PROJECT_INIT_DIR}" -type f \\( -path "*/camunda/*.bpmn" -o -path "*/camunda/*.bpmn20.xml" -o -path "*/camunda/*.dmn" \\) -print0 | sort -z)\n'
        "fi\n"
        "\n"
        'echo "Camunda bootstrap completed."\n'
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


def _resources_by_type(manifest: dict, resource_type: str) -> list[dict]:
    runtime_config = manifest.get("runtimeConfig") or {}
    return [resource for resource in runtime_config.get("resources", []) if resource.get("type") == resource_type]


def _resource_value(resource: dict, name: str, default: str) -> str:
    for item in resource.get("items", []):
        if item.get("name") == name:
            return str(item.get("value") or default)
    return default


def _sql_ident(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in value)
    if not cleaned:
        return "public"
    if cleaned[0].isdigit():
        cleaned = f"schema_{cleaned}"
    return cleaned
