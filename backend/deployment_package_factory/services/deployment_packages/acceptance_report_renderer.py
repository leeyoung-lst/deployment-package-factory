from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath


@dataclass(frozen=True)
class RenderedAcceptanceReport:
    path: PurePosixPath
    content: str
    executable: bool = False


def render_acceptance_report_files(manifest: dict) -> list[RenderedAcceptanceReport]:
    return [RenderedAcceptanceReport(PurePosixPath("docs/acceptance-report.md"), _acceptance_report(manifest))]


def _acceptance_report(manifest: dict) -> str:
    lines = [
        "# Deployment Package Acceptance Report",
        "",
        "## Package",
        "",
        f"- Package ID: {manifest.get('packageId') or '-'}",
        f"- Project: {manifest.get('projectKey') or 'custom'}",
        f"- Product version: {manifest.get('productVersion') or '-'}",
        f"- Source environment: {manifest.get('sourceEnv') or '-'}",
        f"- Target environment: {manifest.get('targetEnv') or '-'}",
        f"- Deploy modes: {_join(manifest.get('deployModes'))}",
        f"- Image mode: {manifest.get('imageMode') or '-'}",
        f"- Database: {manifest.get('database') or '-'}",
        "",
        "## Verification Commands",
        "",
        "- Linux/macOS: `./verify.sh`",
        "- Windows: `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\\verify.ps1`",
        "- Quality gate: `./quality-gate.sh` or `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\\quality-gate.ps1`",
        "",
        "## Images",
        "",
        *_image_summary(manifest),
        "",
        "## Runtime Configuration",
        "",
        *_runtime_config(manifest),
        "",
        "## Initialization Resources",
        "",
        *_runtime_resources(manifest),
        "",
        "## MCP Server Operations",
        "",
        *_mcp_server_operations(manifest),
        "",
        "## Key Files",
        "",
        "- `manifest.json`",
        "- `package-index.json`",
        "- `security/SHA256SUMS`",
        "- `security/image-digest-lock.json`",
        "- `images/images.txt`",
        "- `docker-compose/.env`",
        "- `k8s/secrets.template.yaml`",
        "- `init/run-init.sh`",
        "",
        "## Acceptance Checklist",
        "",
        "- [ ] `verify.sh` or `verify.ps1` passes.",
        "- [ ] Image count and archive count match the selected image mode.",
        "- [ ] Runtime configuration has no unresolved required secrets before installation.",
        "- [ ] Database schema, bucket, and collection resources match the source environment.",
        "- [ ] `install.ps1` or `install.sh` preflight checks pass on the target machine.",
        "",
    ]
    return "\n".join(lines)


def _image_summary(manifest: dict) -> list[str]:
    entries = manifest.get("imageEntries") or []
    if not entries:
        return ["- No image entries were selected."]
    by_group: dict[str, int] = {}
    archive_count = 0
    for item in entries:
        by_group[str(item.get("group") or "unknown")] = by_group.get(str(item.get("group") or "unknown"), 0) + 1
        if item.get("archiveFile"):
            archive_count += 1
    lines = [f"- Total image entries: {len(entries)}", f"- Image archive references: {archive_count}"]
    lines.extend(f"- {group}: {count}" for group, count in sorted(by_group.items()))
    missing_sources = [item for item in entries if item.get("sourceResolvedFrom") == "missing"]
    if missing_sources:
        lines.append(f"- Missing runtime image sources: {len(missing_sources)}")
    return lines


def _runtime_config(manifest: dict) -> list[str]:
    runtime_config = manifest.get("runtimeConfig") or {}
    groups = runtime_config.get("groups") or []
    if not groups:
        return ["- No middleware runtime configuration groups were generated."]
    lines: list[str] = []
    for group in groups:
        lines.append(f"- {group.get('name') or group.get('key')}:")
        for item in group.get("items") or []:
            status = "resolved" if item.get("resolved") else "needs value"
            marker = "sensitive" if item.get("sensitive") else "plain"
            lines.append(f"  - {item.get('envName') or item.get('name')}: {status}, {marker}, source={item.get('source') or '-'}")
    return lines


def _runtime_resources(manifest: dict) -> list[str]:
    resources = (manifest.get("runtimeConfig") or {}).get("resources") or []
    if not resources:
        return ["- No database schema, bucket, or collection resources were generated."]
    lines: list[str] = []
    for resource in resources:
        review = "needs review" if resource.get("needsReview") else "resolved"
        used_by = _join(resource.get("usedBy"))
        lines.append(
            f"- {resource.get('type')}: {resource.get('name')} "
            f"({review}, source={resource.get('source') or '-'}, usedBy={used_by})"
        )
    return lines


def _mcp_server_operations(manifest: dict) -> list[str]:
    services = [item for item in manifest.get("registeredMicroservices") or [] if item.get("mcpServerEnabled")]
    if not services:
        return ["- No MCP-enabled registered microservices are included."]
    lines = [
        "- Set `MCP_API_KEY` before connectivity checks.",
        "- Run `scripts/verify-mcp.sh` or `scripts/verify-mcp.ps1` after services are reachable from the agent network.",
    ]
    for service in services:
        auth = "Bearer API key required" if service.get("mcpRequiresApiKey") else "no API key required"
        lines.append(
            f"- {service.get('serviceKey')}: {service.get('mcpTransport') or 'streamable-http'} "
            f"{service.get('mcpServiceUrl') or service.get('mcpEndpoint') or '/mcp'} ({auth})"
        )
    return lines


def _join(values) -> str:
    items = [str(item) for item in values or [] if item]
    return ", ".join(items) if items else "-"
