from __future__ import annotations

from dataclasses import dataclass, field

from deployment_package_factory.services.microservices.templates_common import TemplateFile


@dataclass(frozen=True)
class FeatureSpec:
    key: str
    name: str
    enabled_field: str
    project_kinds: tuple[str, ...] = ("backend",)
    description: str = ""
    common_required_files: tuple[str, ...] = ()
    stack_required_files: dict[str, tuple[str, ...]] = field(default_factory=dict)
    contract_snippets: tuple[str, ...] = ()

    def enabled(self, context: dict[str, object]) -> bool:
        return bool(context.get(self.enabled_field))

    def required_files(self, tech_stack: str) -> list[str]:
        return [*self.common_required_files, *self.stack_required_files.get(tech_stack, ())]


MCP_SERVER_FEATURE = FeatureSpec(
    key="mcp-server",
    name="MCP Server",
    enabled_field="mcp_server_enabled",
    description="生成 MCP Server 示例项目和配置",
    common_required_files=("config/mcp-server.example.yaml", "docs/MCP_SERVER.md"),
    stack_required_files={
        "python-fastapi": ("src/app/interfaces/mcp/server.py", "src/app/interfaces/http/routes.py"),
        "nodejs-express": ("src/interfaces/mcp/server.ts", "src/interfaces/http/routes.ts"),
        "java-spring-cloud-alibaba": ("src/main/java/com/example/interfaces/McpServerController.java",),
    },
    contract_snippets=("create_demo_item", "/mcp", "protocolVersion", "tools/list"),
)

FEATURE_SPECS = (MCP_SERVER_FEATURE,)


def enabled_feature_specs(context: dict[str, object]) -> list[FeatureSpec]:
    return [item for item in FEATURE_SPECS if item.enabled(context)]


def enabled_feature_specs_from_flags(**flags: object) -> list[FeatureSpec]:
    return enabled_feature_specs(flags)


def scaffold_feature_options() -> list[dict[str, object]]:
    return [
        {
            "key": item.key,
            "name": item.name,
            "field": _camel(item.enabled_field),
            "projectKinds": list(item.project_kinds),
            "description": item.description,
        }
        for item in FEATURE_SPECS
    ]


def _camel(name: str) -> str:
    parts = name.split("_")
    return parts[0] + "".join(item.capitalize() for item in parts[1:])


def mcp_server_env(context: dict[str, object]) -> dict[str, str]:
    return {
        "MCP_SERVER_NAME": f"{context['service_key']}-mcp",
        "MCP_SERVER_TRANSPORT": "streamable-http",
        "MCP_SERVER_ENDPOINT": "/mcp",
        "MCP_ALLOWED_ORIGINS": "",
        "MCP_ALLOWED_HOSTS": "",
    }


def mcp_secret_env(context: dict[str, object]) -> dict[str, str]:
    return {"MCP_API_KEY": "__REPLACE_WITH_MCP_API_KEY__"}


def feature_env_template_lines(context: dict[str, object]) -> list[str]:
    if not MCP_SERVER_FEATURE.enabled(context):
        return []
    values = {**mcp_server_env(context), **mcp_secret_env(context)}
    return [f"{name}={value}" for name, value in values.items()]


def feature_yaml_env_lines(context: dict[str, object], *, indent: str = "  ") -> list[str]:
    if not MCP_SERVER_FEATURE.enabled(context):
        return []
    return [f"{indent}{name}: {value}" for name, value in mcp_server_env(context).items()]


def feature_secret_env_lines(context: dict[str, object], *, indent: str = "  ") -> list[str]:
    if not MCP_SERVER_FEATURE.enabled(context):
        return []
    return [f"{indent}{name}: {value}" for name, value in mcp_secret_env(context).items()]


def feature_required_files(tech_stack: str, *, mcp_server_enabled: bool) -> list[str]:
    return [
        relative
        for feature in enabled_feature_specs_from_flags(mcp_server_enabled=mcp_server_enabled)
        for relative in feature.required_files(tech_stack)
    ]


def render_feature_files(context: dict[str, object]) -> list[TemplateFile]:
    files: list[TemplateFile] = []
    if MCP_SERVER_FEATURE in enabled_feature_specs(context):
        from deployment_package_factory.services.microservices.mcp_templates import mcp_files

        files.extend(mcp_files(context))
    return files
