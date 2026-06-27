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
    projects: dict[str, "ProjectProfile"] = Field(default_factory=dict)
    default_platform: list[str] = Field(default_factory=list)
    allowed_databases: list[str] = Field(default_factory=list)


class BusinessSelection(BaseModel):
    name: str
    profile: str = ""


class ProjectProfile(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    key: str
    name: str
    description: str = ""
    default_version: str = Field(default="", alias="defaultVersion")
    versions: list[str] = Field(default_factory=list)
    default_source_env: str = Field(default="test", alias="defaultSourceEnv")
    default_deploy_modes: list[str] = Field(default_factory=list, alias="defaultDeployModes")
    default_platform_services: list[str] = Field(default_factory=list, alias="defaultPlatformServices")
    default_business_services: list[BusinessSelection] = Field(default_factory=list, alias="defaultBusinessServices")
    default_database: str = Field(default="postgres", alias="defaultDatabase")
    registry: str = ""
    namespace_prefix: str = Field(default="prod", alias="namespacePrefix")
    domain: str = "prod.example.com"
    storage_class: str = Field(default="", alias="storageClass")
    image_tag: str = Field(default="prod", alias="imageTag")
    overlays: list[str] = Field(default_factory=list)


class PackagePreviewRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    project_key: str = Field(default="", alias="projectKey")
    product_version: str = Field(default="", alias="productVersion")
    source_env: str = Field(default="test", alias="sourceEnv")
    deploy_modes: list[str] = Field(default_factory=list, alias="deployModes")
    platform_services: list[str] = Field(default_factory=list, alias="platformServices")
    business_services: list[BusinessSelection] = Field(default_factory=list, alias="businessServices")
    database: str = ""


class TargetProfile(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    env: str = "prod"
    domain: str = "prod.example.com"
    registry: str = ""
    namespace_prefix: str = Field(default="prod", alias="namespacePrefix")
    storage_class: str = Field(default="", alias="storageClass")
    export_images: bool = Field(default=False, alias="exportImages")


class PackageBuildRequest(PackagePreviewRequest):
    image_mode: Literal["image-manifest", "image-archive"] = Field(default="image-manifest", alias="imageMode")
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


TaskStatus = Literal["pending", "running", "completed", "failed", "canceled"]


class PackageTask(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    task_id: str = Field(alias="taskId")
    status: TaskStatus
    progress: int = 0
    message: str = ""
    request: dict
    result: PackageBuildResult | None = None
    artifact_available: bool = Field(default=False, alias="artifactAvailable")
    error: str = ""
    logs: list[str] = Field(default_factory=list)
    worker_id: str = Field(default="", alias="workerId")
    claimed_at: str = Field(default="", alias="claimedAt")
    heartbeat_at: str = Field(default="", alias="heartbeatAt")
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")


class AuditEvent(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    event_id: str = Field(alias="eventId")
    action: str
    target_id: str = Field(default="", alias="targetId")
    status: str
    operator: str = ""
    client_ip: str = Field(default="", alias="clientIp")
    message: str = ""
    metadata: dict = Field(default_factory=dict)
    created_at: str = Field(alias="createdAt")
