from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Iterator

import psycopg
from psycopg.rows import dict_row

from deployment_package_factory.services.microservices.result_metadata import image_ref
from deployment_package_factory.services.microservices.scaffold import MicroserviceScaffoldRequest, MicroserviceScaffoldResult


class MicroserviceRepository:
    def __init__(self, database_url: str) -> None:
        self.database_url = database_url
        self._ensure_schema()

    def upsert(self, request: MicroserviceScaffoldRequest, result: MicroserviceScaffoldResult) -> dict:
        now = _now_iso()
        existing = self.get(request.source_env, request.business_platform_key, request.business_platform_profile, request.service_key)
        created_at = existing["createdAt"] if existing else now
        row = _microservice_payload(request, result, created_at, now)
        with self._connect() as conn:
            conn.execute(
                """
                insert into microservices(
                    source_env, business_platform_key, business_platform_profile,
                    service_key, payload_json, created_at, updated_at
                ) values (%s, %s, %s, %s, %s, %s, %s)
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
                where source_env = %s
                  and business_platform_key = %s
                  and business_platform_profile = %s
                  and service_key = %s
                """,
                (source_env, business_platform_key, business_platform_profile or "", service_key),
            ).fetchone()
        return json.loads(row["payload_json"]) if row else None

    def get_by_project_id(self, project_id: str) -> dict | None:
        with self._connect() as conn:
            rows = conn.execute("select payload_json from microservices").fetchall()
        for row in rows:
            payload = json.loads(row["payload_json"])
            if payload.get("projectId") == project_id:
                return payload
        return None

    def update_delivery(self, project_id: str, delivery: dict[str, object]) -> dict | None:
        existing = self.get_by_project_id(project_id)
        if not existing:
            return None
        existing["delivery"] = delivery
        existing["updatedAt"] = _now_iso()
        with self._connect() as conn:
            conn.execute(
                """
                update microservices set payload_json = %s, updated_at = %s
                where source_env = %s
                  and business_platform_key = %s
                  and business_platform_profile = %s
                  and service_key = %s
                """,
                (
                    json.dumps(existing, ensure_ascii=False),
                    existing["updatedAt"],
                    existing["sourceEnv"],
                    existing["businessPlatformKey"],
                    existing["businessPlatformProfile"],
                    existing["serviceKey"],
                ),
            )
        return existing

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
            where.append("source_env = %s")
            params.append(source_env)
        if business_platform_key:
            where.append("business_platform_key = %s")
            params.append(business_platform_key)
        if business_platform_profile is not None:
            where.append("business_platform_profile = %s")
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

    @contextmanager
    def _connect(self) -> Iterator[psycopg.Connection]:
        with psycopg.connect(self.database_url, row_factory=dict_row) as conn:
            yield conn


def create_microservice_repository(*, database_url: str = "") -> MicroserviceRepository:
    if not database_url.strip():
        raise RuntimeError("DEPLOYMENT_PACKAGE_DATABASE_URL is required for PostgreSQL persistence.")
    return MicroserviceRepository(database_url.strip())


def _microservice_payload(
    request: MicroserviceScaffoldRequest,
    result: MicroserviceScaffoldResult,
    created_at: str,
    updated_at: str,
) -> dict:
    return {
        "projectId": result.project_id,
        "serviceKey": request.service_key,
        "serviceName": request.service_name,
        "description": request.description,
        "projectKind": request.project_kind,
        "techStack": request.tech_stack,
        "microFrontendFramework": request.micro_frontend_framework,
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
        "image": result.image or image_ref(request),
        "gitRepositoryUrl": result.git_repository_url,
        "buildCommand": result.build_command,
        "deployCommand": result.deploy_command,
        "jenkinsJob": result.jenkins_job,
        "delivery": result.delivery,
        "k8sNamespace": request.k8s_namespace or result.business_platform_namespace,
        "artifactName": result.artifact_name,
        "artifactPath": result.artifact_path,
        "sha256": result.sha256,
        "generatedFiles": result.generated_files,
        "status": "registered",
        "createdAt": created_at,
        "updatedAt": updated_at,
    }

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
