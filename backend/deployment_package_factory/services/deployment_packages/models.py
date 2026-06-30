from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Capability(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    key: str
    name: str
    namespace_group: str = Field(alias="namespaceGroup")
    images: list[str] = Field(default_factory=list)
    support_images: list[str] = Field(default_factory=list, alias="supportImages")
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
    port: int = 8080
    data_path: str = Field(default="", alias="dataPath")
    env_template: dict[str, str] = Field(default_factory=dict, alias="envTemplate")
    env_sources: dict[str, dict] = Field(default_factory=dict, alias="envSources")
    compose_environment: dict[str, str] = Field(default_factory=dict, alias="composeEnvironment")
    compose_command: list[str] = Field(default_factory=list, alias="composeCommand")
    compose_healthcheck: dict = Field(default_factory=dict, alias="composeHealthcheck")


class MiddlewareOption(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    key: str
    name: str
    image: str
    port: int = 8080
    data_path: str = Field(default="", alias="dataPath")
    env_template: dict[str, str] = Field(default_factory=dict, alias="envTemplate")
    env_sources: dict[str, dict] = Field(default_factory=dict, alias="envSources")
    compose_environment: dict[str, str] = Field(default_factory=dict, alias="composeEnvironment")
    compose_command: list[str] = Field(default_factory=list, alias="composeCommand")
    compose_healthcheck: dict = Field(default_factory=dict, alias="composeHealthcheck")


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


class TargetProfile(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    env: str = "prod"
    domain: str = "prod.example.com"
    source_registry: str = Field(default="", alias="sourceRegistry")
    source_registry_insecure: bool = Field(default=False, alias="sourceRegistryInsecure")
    registry: str = ""
    namespace_prefix: str = Field(default="prod", alias="namespacePrefix")
    storage_class: str = Field(default="", alias="storageClass")
    export_images: bool = Field(default=False, alias="exportImages")


class PackagePreviewRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    project_key: str = Field(default="", alias="projectKey")
    product_version: str = Field(default="", alias="productVersion")
    source_env: str = Field(default="test", alias="sourceEnv")
    deploy_modes: list[str] = Field(default_factory=list, alias="deployModes")
    platform_services: list[str] = Field(default_factory=list, alias="platformServices")
    business_services: list[BusinessSelection] = Field(default_factory=list, alias="businessServices")
    database: str = ""
    target_profile: TargetProfile = Field(default_factory=TargetProfile, alias="targetProfile")


class PackageBuildRequest(PackagePreviewRequest):
    image_mode: Literal["image-manifest", "image-archive"] = Field(default="image-manifest", alias="imageMode")

    def normalized_for_create(self) -> "PackageBuildRequest":
        if self.image_mode == "image-archive" or self.target_profile.export_images:
            return self._with_image_archive()
        if "image_mode" not in self.model_fields_set:
            return self._with_image_archive()
        return self

    def _with_image_archive(self) -> "PackageBuildRequest":
        return self.model_copy(
            update={
                "image_mode": "image-archive",
                "target_profile": self.target_profile.model_copy(update={"export_images": True}),
            }
        )


class ImageExportEnvironmentCheck(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    available: bool
    export_tool: str = Field(default="", alias="exportTool")
    tool_version: str = Field(default="", alias="toolVersion")
    docker_version: str = Field(default="", alias="dockerVersion")
    message: str = ""


class ResolvedDependency(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    key: str
    name: str
    locked: bool = True
    required_by: list[str] = Field(default_factory=list, alias="requiredBy")
    reason: str = ""
    namespace: str = ""
    source_env: str = Field(default="", alias="sourceEnv")
    status: str = ""


class BusinessPlatformRegistrationRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    source_env: str = Field(alias="sourceEnv")
    key: str
    name: str = ""
    profile: str = ""


class BusinessPlatformRegistrationResult(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    key: str
    name: str
    profile: str = ""
    namespace: str
    source_env: str = Field(alias="sourceEnv")
    status: str


class BusinessPlatform(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    key: str
    name: str
    profile: str = ""
    namespace: str
    source_env: str = Field(alias="sourceEnv")
    status: str = "active"
    metadata: dict = Field(default_factory=dict)
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")


class PackagePreview(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    platform_services: list[ResolvedDependency] = Field(alias="platformServices")
    business_services: list[ResolvedDependency] = Field(alias="businessServices")
    middleware: list[ResolvedDependency]
    database: DatabaseOption
    images: dict[str, list[str]]
    image_entries: list[dict] = Field(default_factory=list, alias="imageEntries")
    warnings: list[str] = Field(default_factory=list)


class PackageBuildResult(BaseModel):
    package_id: str = Field(alias="packageId")
    work_dir: str = Field(alias="workDir")
    artifact_path: str = Field(alias="artifactPath")
    checksum_path: str = Field(default="", alias="checksumPath")
    artifact_size: int = Field(default=0, alias="artifactSize")
    validation_summary: dict = Field(default_factory=dict, alias="validationSummary")
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
