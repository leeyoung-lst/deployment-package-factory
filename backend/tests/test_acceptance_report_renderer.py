from __future__ import annotations

from deployment_package_factory.services.deployment_packages.acceptance_report_renderer import render_acceptance_report_files


def test_render_acceptance_report_files_summarizes_package_inputs() -> None:
    files = render_acceptance_report_files(
        {
            "packageId": "pkg-test",
            "projectKey": "standard-eam",
            "productVersion": "2026.06",
            "sourceEnv": "test",
            "targetEnv": "prod",
            "deployModes": ["k8s", "docker-compose"],
            "imageMode": "image-archive",
            "database": "postgres",
            "imageEntries": [
                {"group": "platform", "archiveFile": "platform.tar"},
                {"group": "business", "archiveFile": "eam.tar"},
            ],
            "runtimeConfig": {
                "groups": [
                    {
                        "key": "postgres",
                        "name": "PostgreSQL",
                        "items": [
                            {"envName": "DATABASE_PASSWORD", "value": "secret-password", "resolved": True, "sensitive": True, "source": "source-secret"},
                        ],
                    }
                ],
                "resources": [
                    {
                        "type": "databaseSchema",
                        "name": "postgres local_ai.eam",
                        "needsReview": False,
                        "source": "pod-env",
                        "usedBy": ["eam"],
                    }
                ],
            },
            "registeredMicroservices": [
                {
                    "serviceKey": "asset-service",
                    "mcpServerEnabled": True,
                    "mcpEndpoint": "/mcp",
                    "mcpTransport": "streamable-http",
                    "mcpRequiresApiKey": True,
                    "mcpServiceUrl": "http://asset-service.test-biz-eam-4x60.svc.cluster.local/mcp",
                }
            ],
        }
    )

    by_path = {item.path.as_posix(): item for item in files}

    assert "docs/acceptance-report.md" in by_path
    content = by_path["docs/acceptance-report.md"].content
    assert "Deployment Package Acceptance Report" in content
    assert "Total image entries: 2" in content
    assert "DATABASE_PASSWORD: resolved, sensitive" in content
    assert "secret-password" not in content
    assert "databaseSchema: postgres local_ai.eam" in content
    assert "powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\\verify.ps1" in content
    assert "MCP Server Operations" in content
    assert "scripts/verify-mcp.sh" in content
    assert "asset-service: streamable-http http://asset-service.test-biz-eam-4x60.svc.cluster.local/mcp" in content
