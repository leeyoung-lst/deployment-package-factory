from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


def _camel(name: str) -> str:
    parts = name.split("_")
    return parts[0] + "".join(w.capitalize() for w in parts[1:])


class Capability(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=_camel)
    key: str
    name: str
    namespace_group: str
    images: list[str] = Field(default_factory=list)
    support_images: list[str] = Field(default_factory=list)
    middleware: list[str] = Field(default_factory=list)
    depends_on: list[str] = Field(default_factory=list)
    required: bool = False
    profile: str = ""


class DatabaseOption(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=_camel)
    key: str
    name: str
    domestic: bool
    image: str
    init_path: str
    port: int = 8080
    data_path: str = ""
    env_template: dict[str, str] = Field(default_factory=dict)
    env_sources: dict[str, dict] = Field(default_factory=dict)
    compose_environment: dict[str, str] = Field(default_factory=dict)
    compose_command: list[str] = Field(default_factory=list)
    compose_healthcheck: dict = Field(default_factory=dict)
    k8s_command: list[str] = Field(default_factory=list)
    k8s_args: list[str] = Field(default_factory=list)


class MiddlewareOption(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=_camel)
    key: str
    name: str
    image: str
    port: int = 8080
    data_path: str = ""
    depends_on: list[str] = Field(default_factory=list)
    env_template: dict[str, str] = Field(default_factory=dict)
    env_sources: dict[str, dict] = Field(default_factory=dict)
    compose_environment: dict[str, str] = Field(default_factory=dict)
    compose_command: list[str] = Field(default_factory=list)
    compose_healthcheck: dict = Field(default_factory=dict)
    k8s_command: list[str] = Field(default_factory=list)
    k8s_args: list[str] = Field(default_factory=list)


class DeploymentCatalog(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=_camel)
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
    model_config = ConfigDict(populate_by_name=True, alias_generator=_camel)
    key: str
    name: str
    description: str = ""
    default_version: str = ""
    versions: list[str] = Field(default_factory=list)
    default_source_env: str = "test"
    default_deploy_modes: list[str] = Field(default_factory=list)
    default_platform_services: list[str] = Field(default_factory=list)
    default_business_services: list[BusinessSelection] = Field(default_factory=list)
    default_database: str = "postgres"
    registry: str = ""
    namespace_prefix: str = "prod"
    domain: str = "prod.example.com"
    storage_class: str = ""
    image_tag: str = "prod"
    overlays: list[str] = Field(default_factory=list)


class TargetProfile(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=_camel)
    env: str = "prod"
    domain: str = "prod.example.com"
    source_registry: str = ""
    source_registry_insecure: bool = False
    registry: str = ""
    namespace_prefix: str = "prod"
    storage_class: str = ""
    export_images: bool = False


class PackagePreviewRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=_camel)
    project_key: str = ""
    product_version: str = ""
    source_env: str = "test"
    deploy_modes: list[str] = Field(default_factory=list)
    platform_services: list[str] = Field(default_factory=list)
    business_services: list[BusinessSelection] = Field(default_factory=list)
    database: str = ""
    target_profile: TargetProfile = Field(default_factory=TargetProfile)


class PackageBuildRequest(PackagePreviewRequest):
    image_mode: Literal["image-manifest", "image-archive"] = "image-manifest"
    runtime_config_overrides: dict[str, str] = Field(default_factory=dict)

    def normalized_for_create(self) -> "PackageBuildRequest":
        if self.image_mode == "image-archive" or self.target_profile.export_images:
            return self.with_image_archive()
        if "image_mode" not in self.model_fields_set:
            return self.with_image_archive()
        return self

    def with_image_archive(self) -> "PackageBuildRequest":
        return self.model_copy(
            update={
                "image_mode": "image-archive",
                "target_profile": self.target_profile.model_copy(update={"export_images": True}),
            }
        )


class ImageExportEnvironmentCheck(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=_camel)

    available: bool
    export_tool: str = ""
    tool_version: str = ""
    docker_version: str = ""
    message: str = ""


class ResolvedDependency(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=_camel)

    key: str
    name: str
    locked: bool = True
    required_by: list[str] = Field(default_factory=list)
    reason: str = ""
    namespace: str = ""
    source_env: str = ""
    status: str = ""


class BusinessPlatformRegistrationRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=_camel)

    source_env: str
    key: str
    name: str = ""
    profile: str = ""


class BusinessPlatformRegistrationResult(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=_camel)

    key: str
    name: str
    profile: str = ""
    namespace: str
    source_env: str
    status: str


class BusinessPlatform(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=_camel)

    key: str
    name: str
    profile: str = ""
    namespace: str
    source_env: str
    status: str = "active"
    metadata: dict = Field(default_factory=dict)
    created_at: str
    updated_at: str


class PackagePreview(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=_camel)

    platform_services: list[ResolvedDependency]
    business_services: list[ResolvedDependency]
    middleware: list[ResolvedDependency]
    database: DatabaseOption
    images: dict[str, list[str]]
    image_entries: list[dict] = Field(default_factory=list)
    runtime_config: dict = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class PackageBuildResult(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=_camel)
    package_id: str
    work_dir: str
    artifact_path: str
    checksum_path: str = ""
    artifact_size: int = 0
    validation_summary: dict = Field(default_factory=dict)
    sha256: str
    manifest: dict


TaskStatus = Literal["pending", "running", "completed", "failed", "canceled"]


class PackageTask(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=_camel)

    task_id: str
    status: TaskStatus
    progress: int = 0
    message: str = ""
    request: dict
    result: PackageBuildResult | None = None
    artifact_available: bool = False
    error: str = ""
    logs: list[str] = Field(default_factory=list)
    worker_id: str = ""
    claimed_at: str = ""
    heartbeat_at: str = ""
    created_at: str
    updated_at: str


class AuditEvent(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=_camel)

    event_id: str
    action: str
    target_id: str = ""
    status: str
    operator: str = ""
    client_ip: str = ""
    message: str = ""
    metadata: dict = Field(default_factory=dict)
    created_at: str
