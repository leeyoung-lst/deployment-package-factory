from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Capability(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    key: str
    name: str
    namespace_group: str = Field(alias="namespaceGroup")
    images: list[str] = Field(default_factory=list)
    middleware: list[str] = Field(default_factory=list)
    depends_on: list[str] = Field(default_factory=list, alias="dependsOn")
    required: bool = False
    profile: str = ""


class DatabaseOption(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    key: str
    name: str
    domestic: bool
    image: str
    init_path: str = Field(alias="initPath")


class MiddlewareOption(BaseModel):
    key: str
    name: str
    image: str


class DeploymentCatalog(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    platform: dict[str, Capability]
    business: dict[str, Capability]
    database_options: dict[str, DatabaseOption]
    middleware: dict[str, MiddlewareOption]
    default_platform: list[str] = Field(default_factory=list)
    allowed_databases: list[str] = Field(default_factory=list)


class BusinessSelection(BaseModel):
    name: str
    profile: str = ""


class PackagePreviewRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    source_env: str = Field(default="test", alias="sourceEnv")
    deploy_modes: list[str] = Field(default_factory=list, alias="deployModes")
    platform_services: list[str] = Field(default_factory=list, alias="platformServices")
    business_services: list[BusinessSelection] = Field(default_factory=list, alias="businessServices")
    database: str = "postgres"


class TargetProfile(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    env: str = "prod"
    domain: str = "prod.example.com"
    registry: str = ""
    namespace_prefix: str = Field(default="prod", alias="namespacePrefix")
    storage_class: str = Field(default="", alias="storageClass")
    export_images: bool = Field(default=False, alias="exportImages")


class PackageBuildRequest(PackagePreviewRequest):
    image_mode: str = Field(default="image-manifest", alias="imageMode")
    target_profile: TargetProfile = Field(default_factory=TargetProfile, alias="targetProfile")


class ResolvedDependency(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    key: str
    name: str
    locked: bool = True
    required_by: list[str] = Field(default_factory=list, alias="requiredBy")
    reason: str = ""


class PackagePreview(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    platform_services: list[ResolvedDependency] = Field(alias="platformServices")
    business_services: list[ResolvedDependency] = Field(alias="businessServices")
    middleware: list[ResolvedDependency]
    database: DatabaseOption
    images: dict[str, list[str]]
    warnings: list[str] = Field(default_factory=list)


class PackageBuildResult(BaseModel):
    package_id: str = Field(alias="packageId")
    work_dir: str = Field(alias="workDir")
    artifact_path: str = Field(alias="artifactPath")
    sha256: str
    manifest: dict


TaskStatus = Literal["pending", "running", "completed", "failed"]


class PackageTask(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    task_id: str = Field(alias="taskId")
    status: TaskStatus
    progress: int = 0
    message: str = ""
    request: dict
    result: PackageBuildResult | None = None
    error: str = ""
    logs: list[str] = Field(default_factory=list)
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")
