from __future__ import annotations

import shutil
from pathlib import Path
from typing import Protocol

import psycopg
from psycopg.rows import dict_row
from pydantic import BaseModel, ConfigDict, Field


RESET_CONFIRMATION = "RESET deployment-package-factory"
RESET_TABLES = {
    "package_tasks": "packageTasks",
    "audit_events": "auditEvents",
    "business_platforms": "businessPlatforms",
    "microservices": "microservices",
    "system_settings": "systemSettings",
}


class EnvironmentResetOptions(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    package_tasks: bool = Field(default=True, alias="packageTasks")
    audit_events: bool = Field(default=True, alias="auditEvents")
    business_platforms: bool = Field(default=True, alias="businessPlatforms")
    microservices: bool = True
    package_artifacts: bool = Field(default=True, alias="packageArtifacts")
    package_work_dirs: bool = Field(default=True, alias="packageWorkDirs")
    system_settings: bool = Field(default=False, alias="systemSettings")


class EnvironmentResetRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    options: EnvironmentResetOptions = Field(default_factory=EnvironmentResetOptions)
    confirmation: str = ""


class ResetTableSummary(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str
    selected: bool
    existing_rows: int = Field(default=0, alias="existingRows")
    deleted_rows: int = Field(default=0, alias="deletedRows")


class ResetPathSummary(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str
    path: str
    selected: bool
    exists: bool = False
    files: int = 0
    directories: int = 0
    bytes: int = 0
    deleted_files: int = Field(default=0, alias="deletedFiles")
    deleted_directories: int = Field(default=0, alias="deletedDirectories")
    freed_bytes: int = Field(default=0, alias="freedBytes")


class EnvironmentResetPreview(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    namespace: str = "deployment-package-factory"
    confirmation_phrase: str = Field(default=RESET_CONFIRMATION, alias="confirmationPhrase")
    dry_run: bool = Field(default=True, alias="dryRun")
    tables: list[ResetTableSummary] = Field(default_factory=list)
    paths: list[ResetPathSummary] = Field(default_factory=list)
    total_rows: int = Field(default=0, alias="totalRows")
    selected_rows: int = Field(default=0, alias="selectedRows")
    deleted_rows: int = Field(default=0, alias="deletedRows")
    total_files: int = Field(default=0, alias="totalFiles")
    selected_files: int = Field(default=0, alias="selectedFiles")
    deleted_files: int = Field(default=0, alias="deletedFiles")
    total_bytes: int = Field(default=0, alias="totalBytes")
    selected_bytes: int = Field(default=0, alias="selectedBytes")
    freed_bytes: int = Field(default=0, alias="freedBytes")


class ResetAuditRepository(Protocol):
    def record(
        self,
        *,
        action: str,
        status: str,
        target_id: str = "",
        operator: str = "",
        client_ip: str = "",
        message: str = "",
        metadata: dict | None = None,
    ):
        ...


def preview_environment_reset(database_url: str, output_dir: Path, options: EnvironmentResetOptions) -> EnvironmentResetPreview:
    result = EnvironmentResetPreview(dry_run=True)
    result.tables = _table_summaries(database_url, options)
    result.paths = _path_summaries(output_dir, options)
    return _with_totals(result)


def execute_environment_reset(database_url: str, output_dir: Path, request: EnvironmentResetRequest) -> EnvironmentResetPreview:
    if request.confirmation != RESET_CONFIRMATION:
        raise ValueError(f"Confirmation must be exactly: {RESET_CONFIRMATION}")
    result = EnvironmentResetPreview(dry_run=False)
    result.tables = _delete_tables(database_url, request.options)
    result.paths = _delete_paths(output_dir, request.options)
    return _with_totals(result)


def _table_summaries(database_url: str, options: EnvironmentResetOptions) -> list[ResetTableSummary]:
    selected = _selected_tables(options)
    rows: list[ResetTableSummary] = []
    with psycopg.connect(database_url, row_factory=dict_row) as conn:
        for table, name in RESET_TABLES.items():
            rows.append(
                ResetTableSummary(
                    name=name,
                    selected=table in selected,
                    existingRows=_count_table(conn, table),
                )
            )
    return rows


def _delete_tables(database_url: str, options: EnvironmentResetOptions) -> list[ResetTableSummary]:
    selected = _selected_tables(options)
    rows: list[ResetTableSummary] = []
    with psycopg.connect(database_url, row_factory=dict_row) as conn:
        for table, name in RESET_TABLES.items():
            existing_rows = _count_table(conn, table)
            deleted_rows = 0
            if table in selected:
                deleted_rows = _delete_table(conn, table, existing_rows)
            rows.append(
                ResetTableSummary(
                    name=name,
                    selected=table in selected,
                    existingRows=existing_rows,
                    deletedRows=deleted_rows,
                )
            )
        conn.commit()
    return rows


def _path_summaries(output_dir: Path, options: EnvironmentResetOptions) -> list[ResetPathSummary]:
    return [
        _scan_path("packageArtifacts", output_dir / "artifacts", selected=options.package_artifacts),
        _scan_path("packageWorkDirs", output_dir / "work", selected=options.package_work_dirs),
    ]


def _delete_paths(output_dir: Path, options: EnvironmentResetOptions) -> list[ResetPathSummary]:
    output_root = output_dir.resolve()
    summaries: list[ResetPathSummary] = []
    for summary in _path_summaries(output_dir, options):
        if not summary.selected:
            summaries.append(summary)
            continue
        path = Path(summary.path).resolve()
        _ensure_child_path(output_root, path)
        path.mkdir(parents=True, exist_ok=True)
        deleted_files = 0
        deleted_directories = 0
        freed_bytes = 0
        for child in list(path.iterdir()):
            if child.is_file() or child.is_symlink():
                freed_bytes += _safe_size(child)
                child.unlink(missing_ok=True)
                deleted_files += 1
            elif child.is_dir():
                freed_bytes += _path_size(child)
                shutil.rmtree(child)
                deleted_directories += 1
        summaries.append(
            summary.model_copy(
                update={
                    "deleted_files": deleted_files,
                    "deleted_directories": deleted_directories,
                    "freed_bytes": freed_bytes,
                }
            )
        )
    return summaries


def _selected_tables(options: EnvironmentResetOptions) -> set[str]:
    selected: set[str] = set()
    if options.package_tasks:
        selected.add("package_tasks")
    if options.audit_events:
        selected.add("audit_events")
    if options.business_platforms:
        selected.add("business_platforms")
    if options.microservices:
        selected.add("microservices")
    if options.system_settings:
        selected.add("system_settings")
    return selected


def _count_table(conn: psycopg.Connection, table: str) -> int:
    try:
        return int(conn.execute(f"select count(*) as count from {table}").fetchone()["count"])
    except psycopg.errors.UndefinedTable:
        conn.rollback()
        return 0


def _delete_table(conn: psycopg.Connection, table: str, fallback_count: int) -> int:
    try:
        with conn.cursor() as cursor:
            cursor.execute(f"delete from {table}")
            return cursor.rowcount if cursor.rowcount >= 0 else fallback_count
    except psycopg.errors.UndefinedTable:
        conn.rollback()
        return 0


def _scan_path(name: str, path: Path, *, selected: bool) -> ResetPathSummary:
    resolved = path.resolve()
    if not resolved.exists():
        return ResetPathSummary(name=name, path=str(resolved), selected=selected, exists=False)
    files = 0
    directories = 0
    total_bytes = 0
    for item in resolved.rglob("*"):
        if item.is_file():
            files += 1
            total_bytes += _safe_size(item)
        elif item.is_dir():
            directories += 1
    return ResetPathSummary(
        name=name,
        path=str(resolved),
        selected=selected,
        exists=True,
        files=files,
        directories=directories,
        bytes=total_bytes,
    )


def _path_size(path: Path) -> int:
    total = 0
    for item in path.rglob("*"):
        if item.is_file():
            total += _safe_size(item)
    return total


def _safe_size(path: Path) -> int:
    try:
        return path.stat().st_size
    except FileNotFoundError:
        return 0


def _ensure_child_path(root: Path, child: Path) -> None:
    if root == child or root not in child.parents:
        raise ValueError(f"Refusing to clean path outside output directory: {child}")


def _with_totals(result: EnvironmentResetPreview) -> EnvironmentResetPreview:
    total_rows = sum(item.existing_rows for item in result.tables)
    selected_rows = sum(item.existing_rows for item in result.tables if item.selected)
    deleted_rows = sum(item.deleted_rows for item in result.tables)
    total_files = sum(item.files for item in result.paths)
    selected_files = sum(item.files for item in result.paths if item.selected)
    deleted_files = sum(item.deleted_files for item in result.paths)
    total_bytes = sum(item.bytes for item in result.paths)
    selected_bytes = sum(item.bytes for item in result.paths if item.selected)
    freed_bytes = sum(item.freed_bytes for item in result.paths)
    return result.model_copy(
        update={
            "total_rows": total_rows,
            "selected_rows": selected_rows,
            "deleted_rows": deleted_rows,
            "total_files": total_files,
            "selected_files": selected_files,
            "deleted_files": deleted_files,
            "total_bytes": total_bytes,
            "selected_bytes": selected_bytes,
            "freed_bytes": freed_bytes,
        }
    )
