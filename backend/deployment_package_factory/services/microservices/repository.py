from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from deployment_package_factory.services.microservices.scaffold import MicroserviceScaffoldRequest, MicroserviceScaffoldResult


class MicroserviceRepository:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def upsert(self, request: MicroserviceScaffoldRequest, result: MicroserviceScaffoldResult) -> dict:
        now = _now_iso()
        existing = self.get(request.source_env, request.business_platform_key, request.business_platform_profile, request.service_key)
        created_at = existing["createdAt"] if existing else now
        row = {
            "projectId": result.project_id,
            "serviceKey": request.service_key,
            "serviceName": request.service_name,
            "description": request.description,
            "projectKind": request.project_kind,
            "techStack": request.tech_stack,
            "port": request.port,
            "middleware": request.middleware,
            "sourceEnv": request.source_env,
            "businessPlatformKey": request.business_platform_key,
            "businessPlatformProfile": request.business_platform_profile,
            "businessPlatformName": result.business_platform_name,
            "businessPlatformNamespace": result.business_platform_namespace,
            "gitGroup": request.git_group,
            "imageRegistry": request.image_registry,
            "imageNamespace": request.image_namespace,
            "image": _image_ref(request),
            "k8sNamespace": request.k8s_namespace or result.business_platform_namespace,
            "artifactName": result.artifact_name,
            "artifactPath": result.artifact_path,
            "sha256": result.sha256,
            "generatedFiles": result.generated_files,
            "status": "registered",
            "createdAt": created_at,
            "updatedAt": now,
        }
        with self._connect() as conn:
            conn.execute(
                """
                insert into microservices(
                    source_env, business_platform_key, business_platform_profile,
                    service_key, payload_json, created_at, updated_at
                ) values (?, ?, ?, ?, ?, ?, ?)
                on conflict(source_env, business_platform_key, business_platform_profile, service_key)
                do update set
                    payload_json = excluded.payload_json,
                    updated_at = excluded.updated_at
                """,
                (
                    row["sourceEnv"],
                    row["businessPlatformKey"],
                    row["businessPlatformProfile"],
                    row["serviceKey"],
                    json.dumps(row, ensure_ascii=False),
                    created_at,
                    now,
                ),
            )
        return row

    def get(self, source_env: str, business_platform_key: str, business_platform_profile: str, service_key: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                select payload_json from microservices
                where source_env = ?
                  and business_platform_key = ?
                  and business_platform_profile = ?
                  and service_key = ?
                """,
                (source_env, business_platform_key, business_platform_profile or "", service_key),
            ).fetchone()
        return json.loads(row["payload_json"]) if row else None

    def list(
        self,
        *,
        source_env: str | None = None,
        business_platform_key: str | None = None,
        business_platform_profile: str | None = None,
    ) -> list[dict]:
        where: list[str] = []
        params: list[str] = []
        if source_env:
            where.append("source_env = ?")
            params.append(source_env)
        if business_platform_key:
            where.append("business_platform_key = ?")
            params.append(business_platform_key)
        if business_platform_profile is not None:
            where.append("business_platform_profile = ?")
            params.append(business_platform_profile)
        query = "select payload_json from microservices"
        if where:
            query += " where " + " and ".join(where)
        query += " order by source_env, business_platform_key, business_platform_profile, service_key"
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [json.loads(row["payload_json"]) for row in rows]

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                create table if not exists microservices (
                    source_env text not null,
                    business_platform_key text not null,
                    business_platform_profile text not null default '',
                    service_key text not null,
                    payload_json text not null,
                    created_at text not null,
                    updated_at text not null,
                    primary key(source_env, business_platform_key, business_platform_profile, service_key)
                )
                """
            )
            conn.execute("create index if not exists idx_microservices_platform on microservices(source_env, business_platform_key)")

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn


def _image_ref(request: MicroserviceScaffoldRequest) -> str:
    return f"{request.image_registry.rstrip('/')}/{request.image_namespace.strip('/')}/{request.service_key}"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
