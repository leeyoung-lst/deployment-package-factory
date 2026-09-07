from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import PurePosixPath


@dataclass(frozen=True)
class RenderedMcpVerifyFile:
    path: PurePosixPath
    content: str
    executable: bool = False


def render_mcp_verify_files(manifest: dict) -> list[RenderedMcpVerifyFile]:
    services = [item for item in manifest.get("registeredMicroservices") or [] if item.get("mcpServerEnabled")]
    if not services:
        return []
    return [
        RenderedMcpVerifyFile(PurePosixPath("scripts/verify-mcp.sh"), _verify_mcp_sh(services), executable=True),
        RenderedMcpVerifyFile(PurePosixPath("scripts/verify-mcp.ps1"), _verify_mcp_ps1(services)),
    ]


def _verify_mcp_sh(services: list[dict]) -> str:
    services_json = json.dumps(_service_specs(services), ensure_ascii=False)
    return (
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        f"MCP_SERVICES='{services_json}'\n"
        "MCP_API_KEY=\"${MCP_API_KEY:-}\"\n"
        "python3 - \"$MCP_SERVICES\" \"$MCP_API_KEY\" <<'PY'\n"
        "import json\n"
        "import os\n"
        "import sys\n"
        "import urllib.request\n"
        "\n"
        "services = json.loads(sys.argv[1])\n"
        "api_key = sys.argv[2]\n"
        "payload = json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list', 'params': {}}).encode('utf-8')\n"
        "for service in services:\n"
        "    if service['requiresApiKey'] and not api_key:\n"
        "        raise SystemExit(f\"MCP_API_KEY is required for {service['serviceKey']}\")\n"
        "    if service['requiresApiKey'] and api_key.startswith('__REPLACE_WITH_'):\n"
        "        raise SystemExit(f\"Replace MCP_API_KEY before verifying {service['serviceKey']}\")\n"
        "    url = os.getenv(service.get('urlOverrideEnv') or '', '').strip() or service['url']\n"
        "    request = urllib.request.Request(url, data=payload, headers={'Content-Type': 'application/json'}, method='POST')\n"
        "    if service['requiresApiKey']:\n"
        "        request.add_header('Authorization', f'Bearer {api_key}')\n"
        "    with urllib.request.urlopen(request, timeout=10) as response:\n"
        "        body = json.loads(response.read().decode('utf-8'))\n"
        "    tools = body.get('result', {}).get('tools')\n"
        "    if not isinstance(tools, list):\n"
        "        raise SystemExit(f\"{service['serviceKey']} did not return MCP tools/list\")\n"
        "    print(f\"{service['serviceKey']} MCP tools/list ok ({len(tools)} tools)\")\n"
        "PY\n"
    )


def _verify_mcp_ps1(services: list[dict]) -> str:
    services_json = json.dumps(_service_specs(services), ensure_ascii=False).replace("'", "''")
    return (
        "$ErrorActionPreference = 'Stop'\n"
        f"$services = '{services_json}' | ConvertFrom-Json\n"
        "$apiKey = $env:MCP_API_KEY\n"
        "$payload = @{ jsonrpc = '2.0'; id = 1; method = 'tools/list'; params = @{} } | ConvertTo-Json -Depth 6\n"
        "foreach ($service in @($services)) {\n"
        "  if ($service.requiresApiKey -and [string]::IsNullOrWhiteSpace($apiKey)) { throw \"MCP_API_KEY is required for $($service.serviceKey)\" }\n"
        "  if ($service.requiresApiKey -and $apiKey.StartsWith('__REPLACE_WITH_')) { throw \"Replace MCP_API_KEY before verifying $($service.serviceKey)\" }\n"
        "  $override = if ($service.urlOverrideEnv) { [Environment]::GetEnvironmentVariable($service.urlOverrideEnv) } else { '' }\n"
        "  $url = if (-not [string]::IsNullOrWhiteSpace($override)) { $override } else { $service.url }\n"
        "  $headers = @{ 'Content-Type' = 'application/json' }\n"
        "  if ($service.requiresApiKey) { $headers['Authorization'] = \"Bearer $apiKey\" }\n"
        "  $result = Invoke-RestMethod -Method Post -Uri $url -Headers $headers -Body $payload -TimeoutSec 10\n"
        "  if (-not $result.result.tools) { throw \"$($service.serviceKey) did not return MCP tools/list\" }\n"
        "  Write-Host \"$($service.serviceKey) MCP tools/list ok\"\n"
        "}\n"
    )


def _service_specs(services: list[dict]) -> list[dict]:
    return [
        {
            "serviceKey": service_key,
            "url": item.get("mcpServiceUrl") or item.get("mcpEndpoint") or "/mcp",
            "urlOverrideEnv": f"MCP_{_env_key(service_key)}_URL",
            "requiresApiKey": bool(item.get("mcpRequiresApiKey")),
        }
        for item in services
        for service_key in [str(item.get("serviceKey") or "service")]
    ]


def _env_key(value: str) -> str:
    return "".join(char.upper() if char.isalnum() else "_" for char in value).strip("_")
