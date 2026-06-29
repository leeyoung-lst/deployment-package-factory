from __future__ import annotations

import json
import re
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Iterator

import psycopg
from psycopg.rows import dict_row
from pydantic import BaseModel, ConfigDict, Field, field_validator

IMAGE_PATH_RE = r"^[a-z0-9]+(?:[._-][a-z0-9]+)*(?:/[a-z0-9]+(?:[._-][a-z0-9]+)*)*$"


class GitSettings(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    base_url: str = Field(default="", alias="baseUrl")
    group: str = "business-services"
    username: str = ""
    email: str = ""

    @field_validator("base_url", "username", "email")
    @classmethod
    def trim_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("group")
    @classmethod
    def normalize_group(cls, value: str) -> str:
        normalized = value.strip().strip("/").lower()
        if not normalized:
            raise ValueError("git.group is required")
        if not re.fullmatch(IMAGE_PATH_RE, normalized):
            raise ValueError("git.group must contain lowercase path segments")
        return normalized


class HarborSettings(BaseModel):
    registry: str = "registry.local"
    project: str = "business"
    username: str = ""
    insecure: bool = False

    @field_validator("registry")
    @classmethod
    def normalize_registry(cls, value: str) -> str:
        normalized = value.strip().rstrip("/")
        if not normalized:
            raise ValueError("harbor.registry is required")
        if "/" in normalized or any(char.isspace() for char in normalized):
            raise ValueError("harbor.registry must be a registry host, optionally with port")
        return normalized

    @field_validator("project")
    @classmethod
    def normalize_project(cls, value: str) -> str:
        normalized = value.strip().strip("/").lower()
        if not normalized:
            raise ValueError("harbor.project is required")
        if not re.fullmatch(IMAGE_PATH_RE, normalized):
            raise ValueError("harbor.project must contain lowercase path segments")
        return normalized

    @field_validator("username")
    @classmethod
    def trim_username(cls, value: str) -> str:
        return value.strip()


class JenkinsSettings(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    base_url: str = Field(default="", alias="baseUrl")
    folder: str = "business-services"
    username: str = ""

    @field_validator("base_url", "username")
    @classmethod
    def trim_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("folder")
    @classmethod
    def normalize_folder(cls, value: str) -> str:
        normalized = value.strip().strip("/").lower()
        if normalized and not re.fullmatch(IMAGE_PATH_RE, normalized):
            raise ValueError("jenkins.folder must contain lowercase path segments")
        return normalized


class SystemSettings(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    git: GitSettings = Field(default_factory=GitSettings)
    harbor: HarborSettings = Field(default_factory=HarborSettings)
    jenkins: JenkinsSettings = Field(default_factory=JenkinsSettings)
    updated_at: str = Field(default="", alias="updatedAt")


class SystemSettingsRepository:
    def __init__(self, database_url: str) -> None:
        self.database_url = database_url
        self._ensure_schema()

    def get(self) -> SystemSettings:
        with self._connect() as conn:
            row = conn.execute("select payload_json, updated_at from system_settings where key = %s", ("global",)).fetchone()
        if not row:
            return SystemSettings()
        payload = json.loads(row["payload_json"])
        payload["updatedAt"] = row["updated_at"]
        return SystemSettings.model_validate(payload)

    def update(self, settings: SystemSettings) -> SystemSettings:
        now = datetime.now(timezone.utc).isoformat()
        payload = settings.model_dump(by_alias=True, exclude={"updated_at"})
        with self._connect() as conn:
            conn.execute(
                """
                insert into system_settings(key, payload_json, updated_at)
                values (%s, %s, %s)
                on conflict(key) do update set
                    payload_json = excluded.payload_json,
                    updated_at = excluded.updated_at
                """,
                ("global", json.dumps(payload, ensure_ascii=False), now),
            )
        payload["updatedAt"] = now
        return SystemSettings.model_validate(payload)

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                create table if not exists system_settings (
                    key text primary key,
                    payload_json text not null,
                    updated_at text not null
                )
                """
            )

    @contextmanager
    def _connect(self) -> Iterator[psycopg.Connection]:
        with psycopg.connect(self.database_url, row_factory=dict_row) as conn:
            yield conn


def create_system_settings_repository(*, database_url: str = "") -> SystemSettingsRepository:
    if not database_url.strip():
        raise RuntimeError("DEPLOYMENT_PACKAGE_DATABASE_URL is required for PostgreSQL persistence.")
    return SystemSettingsRepository(database_url.strip())
