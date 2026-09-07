from __future__ import annotations

from deployment_package_factory.services.deployment_packages.mcp_verify_renderer import render_mcp_verify_files


def test_render_mcp_verify_files_exports_scripts_for_mcp_services() -> None:
    files = render_mcp_verify_files(
        {
            "registeredMicroservices": [
                {
                    "serviceKey": "asset-service",
                    "mcpServerEnabled": True,
                    "mcpEndpoint": "/mcp",
                    "mcpRequiresApiKey": True,
                    "mcpServiceUrl": "http://asset-service.test-biz-eam-4x60.svc.cluster.local/mcp",
                }
            ]
        }
    )
    by_path = {item.path.as_posix(): item for item in files}

    assert "scripts/verify-mcp.sh" in by_path
    assert "scripts/verify-mcp.ps1" in by_path
    assert by_path["scripts/verify-mcp.sh"].executable is True
    assert "tools/list" in by_path["scripts/verify-mcp.sh"].content
    assert "MCP_API_KEY is required for" in by_path["scripts/verify-mcp.sh"].content
    assert "Replace MCP_API_KEY before verifying" in by_path["scripts/verify-mcp.sh"].content
    assert "MCP_ASSET_SERVICE_URL" in by_path["scripts/verify-mcp.sh"].content
    assert "asset-service.test-biz-eam-4x60.svc.cluster.local/mcp" in by_path["scripts/verify-mcp.ps1"].content


def test_render_mcp_verify_files_skips_when_no_mcp_services() -> None:
    assert render_mcp_verify_files({"registeredMicroservices": [{"serviceKey": "asset-service"}]}) == []
