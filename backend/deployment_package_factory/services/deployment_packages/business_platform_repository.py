from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from deployment_package_factory.services.deployment_packages.kubernetes_runtime import RegisteredBusinessPlatform
from deployment_package_factory.services.deployment_packages.models import BusinessPlatform
from deployment_package_factory.services.deployment_packages.task_repository import DEFAULT_TASK_DB


DEFAULT_BUSINESS_PLATFORM_DB = DEFAULT_TASK_DB.with_name("deployment-package-business-platforms.sqlite3")


class BusinessPlatformRepository:
    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or DEFAULT_BUSINESS_PLATFORM_DB
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def upsert_registered(self, item: RegisteredBusinessPlatform, metadata: dict | None = None) -> BusinessPlatform:
        existing = self.get(item.source_env, item.key, item.profile)
        now = _now_iso()
        created_at = existing.created_at if existing else now
        platform = BusinessPlatform(
            key=item.key,
            name=item.name,
            profile=item.profile,
            namespace=item.namespace,
            sourceEnv=item.source_env,
            status=item.status,
            metadata=metadata or {},
            createdAt=created_at,
            updatedAt=now,
        )
        with self._connect() as conn:
            conn.execute(
                """
                insert into business_platforms(
                    source_env, business_key, profile, name, namespace,
                    status, metadata_json, created_at, updated_at
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?)
                on conflict(source_env, business_key, profile) do update set
                    name = excluded.name,
                    namespace = excluded.namespace,
                    status = excluded.status,
                    metadata_json = excluded.metadata_json,
                    updated_at = excluded.updated_at
                """,
                _platform_to_row(platform),
            )
        return platform

    def get(self, source_env: str, key: str, profile: str = "") -> BusinessPlatform | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                select * from business_platforms
                where source_env = ? and business_key = ? and profile = ?
                """,
                (source_env, key, profile or ""),
            ).fetchone()
        return _platform_from_row(row) if row else None

    def resolve(self, source_env: str, key: str, profile: str = "") -> BusinessPlatform:
        if profile:
            platform = self.get(source_env, key, profile)
            if platform is None:
                raise KeyError(f"{source_env}/{key}/{profile}")
            return platform
        matches = [item for item in self.list(source_env, include_disabled=True) if item.key == key]
        if not matches:
            raise KeyError(f"{source_env}/{key}")
        if len(matches) > 1:
            profiles = ", ".join(item.profile or "<default>" for item in matches)
            raise ValueError(f"Business platform {source_env}/{key} has multiple profiles: {profiles}.")
        return matches[0]

    def list(self, source_env: str | None = None, *, include_disabled: bool = False) -> list[BusinessPlatform]:
        where: list[str] = []
        params: list[str] = []
        if source_env:
            where.append("source_env = ?")
            params.append(source_env)
        if not include_disabled:
            where.append("status != 'disabled'")
        query = "select * from business_platforms"
        if where:
            query += " where " + " and ".join(where)
        query += " order by source_env, business_key, profile, namespace"
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [_platform_from_row(row) for row in rows]

    def disable(self, source_env: str, key: str, profile: str = "") -> BusinessPlatform:
        platform = self.resolve(source_env, key, profile)
        updated = platform.model_copy(update={"status": "disabled", "updated_at": _now_iso()})
        with self._connect() as conn:
            conn.execute(
                """
                update business_platforms
                set status = ?, updated_at = ?
                where source_env = ? and business_key = ? and profile = ?
                """,
                (updated.status, updated.updated_at, updated.source_env, updated.key, updated.profile),
            )
        return updated

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                create table if not exists business_platforms (
                    source_env text not null,
                    business_key text not null,
                    profile text not null default '',
                    name text not null,
                    namespace text not null,
                    status text not null,
                    metadata_json text not null,
                    created_at text not null,
                    updated_at text not null,
                    primary key(source_env, business_key, profile)
                )
                """
            )
            conn.execute("create index if not exists idx_business_platforms_status on business_platforms(status)")
            conn.execute("create index if not exists idx_business_platforms_namespace on business_platforms(namespace)")

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn


def _platform_to_row(platform: BusinessPlatform) -> tuple:
    return (
        platform.source_env,
        platform.key,
        platform.profile,
        platform.name,
        platform.namespace,
        platform.status,
        json.dumps(platform.metadata, ensure_ascii=False),
        platform.created_at,
        platform.updated_at,
    )


def _platform_from_row(row: sqlite3.Row) -> BusinessPlatform:
    return BusinessPlatform(
        key=row["business_key"],
        name=row["name"],
        profile=row["profile"],
        namespace=row["namespace"],
        sourceEnv=row["source_env"],
        status=row["status"],
        metadata=json.loads(row["metadata_json"]),
        createdAt=row["created_at"],
        updatedAt=row["updated_at"],
    )


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
