from __future__ import annotations

from pathlib import PurePosixPath

from deployment_package_factory.services.microservices.templates_common import TemplateFile


def mcp_files(context: dict[str, object]) -> list[TemplateFile]:
    renderers = {
        "python-fastapi": python_mcp_files,
        "nodejs-express": node_mcp_files,
        "java-spring-cloud-alibaba": java_mcp_files,
    }
    renderer = renderers.get(str(context["tech_stack"]))
    return renderer(context) if renderer else []


def mcp_config(context: dict[str, object]) -> str:
    return f"""server:
  name: {context['service_key']}-mcp
  transport: streamable-http
  endpoint: /mcp
tools:
  - name: describe_service
    description: Return service metadata for agent discovery.
  - name: create_demo_item
    description: Create a demo domain item from a name.
"""


def mcp_readme(context: dict[str, object]) -> str:
    return f"""# MCP Server Example

This project includes an MCP server example for {context['service_name']}.

## Configuration

Runtime defaults are in `config/mcp-server.example.yaml` and `.env.template`.

## Agent connection

- URL: `http://<service-host>/mcp`
- Transport: `streamable-http`
- Header: `Authorization: Bearer <MCP_API_KEY>`

For local development, copy `.env.template` to `.env`, replace `MCP_API_KEY`, and connect the Agent to:

```text
http://127.0.0.1:{context['port']}/mcp
```

For in-cluster access, use the Kubernetes service DNS name:

```text
http://{context['service_key']}.{context['k8s_namespace']}.svc.cluster.local/mcp
```

For an Ingress, port-forward, or Agent running outside the cluster, point the Agent to that reachable URL and keep the path `/mcp`.

Agent configuration example:

```json
{{
  "mcpServers": {{
    "{context['service_key']}": {{
      "url": "http://{context['service_key']}.{context['k8s_namespace']}.svc.cluster.local/mcp",
      "headers": {{
        "Authorization": "Bearer <MCP_API_KEY>"
      }}
    }}
  }}
}}
```

## Production safety

- Always replace `MCP_API_KEY` before exposing `/mcp`.
- Do not use `__REPLACE_WITH_MCP_API_KEY__` as a runtime value; generated verification scripts reject placeholder keys.
- Set `MCP_ALLOWED_ORIGINS` and `MCP_ALLOWED_HOSTS` when the service is reachable through Ingress.
- Do not expose `/mcp` publicly without TLS, authentication, and an allowlist.

## Deployment smoke test

After deployment, run the package-level verifier from the deployment package root:

```bash
export MCP_API_KEY='<real-api-key>'
export MCP_{str(context['service_key']).upper().replace('-', '_')}_URL='http://<reachable-host>/mcp' # optional override
./scripts/verify-mcp.sh
```

## Local smoke test

Start the service normally, then send a JSON-RPC MCP request:

```bash
curl -X POST http://127.0.0.1:{context['port']}/mcp \\
  -H 'Content-Type: application/json' \\
  -H 'Authorization: Bearer <MCP_API_KEY>' \\
  -d '{{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{{}}}}'
```

The generated code keeps MCP wiring under the interfaces layer. Move reusable tool behavior into domain or application services as it becomes business logic.
"""


def python_mcp_files(context: dict[str, object]) -> list[TemplateFile]:
    return [
        TemplateFile(PurePosixPath("config/mcp-server.example.yaml"), mcp_config(context)),
        TemplateFile(PurePosixPath("docs/MCP_SERVER.md"), mcp_readme(context)),
        TemplateFile(PurePosixPath("src/app/interfaces/mcp/__init__.py"), ""),
        TemplateFile(PurePosixPath("src/app/interfaces/mcp/server.py"), python_mcp_server(context)),
    ]


def node_mcp_files(context: dict[str, object]) -> list[TemplateFile]:
    return [
        TemplateFile(PurePosixPath("config/mcp-server.example.yaml"), mcp_config(context)),
        TemplateFile(PurePosixPath("docs/MCP_SERVER.md"), mcp_readme(context)),
        TemplateFile(PurePosixPath("src/interfaces/mcp/server.ts"), node_mcp_server(context)),
    ]


def java_mcp_files(context: dict[str, object]) -> list[TemplateFile]:
    return [
        TemplateFile(PurePosixPath("config/mcp-server.example.yaml"), mcp_config(context)),
        TemplateFile(PurePosixPath("docs/MCP_SERVER.md"), mcp_readme(context)),
        TemplateFile(PurePosixPath("src/main/java/com/example/interfaces/McpServerController.java"), java_mcp_controller(context)),
    ]


def python_mcp_server(context: dict[str, object]) -> str:
    return f"""from app.application.use_cases import create_demo_item
from app.config import settings


def handle_mcp_request(payload: dict) -> dict:
    method = payload.get("method")
    request_id = payload.get("id")
    if method == "initialize":
        result = {{
            "protocolVersion": "2025-06-18",
            "serverInfo": {{"name": settings.mcp_server_name, "version": "0.1.0"}},
            "capabilities": {{"tools": {{}}}},
        }}
    elif method == "tools/list":
        result = {{"tools": mcp_tools()}}
    elif method == "tools/call":
        result = call_tool(payload.get("params") or {{}})
    elif method == "notifications/initialized":
        return {{"jsonrpc": "2.0", "result": None, "id": request_id}}
    else:
        return _error(request_id, -32601, f"Unsupported MCP method: {{method}}")
    return {{"jsonrpc": "2.0", "id": request_id, "result": result}}


def mcp_tools() -> list[dict]:
    return [
        {{
            "name": "describe_service",
            "description": "Return service metadata for agent discovery.",
            "inputSchema": {{"type": "object", "properties": {{}}}},
        }},
        {{
            "name": "create_demo_item",
            "description": "Create a demo domain item from a name.",
            "inputSchema": {{
                "type": "object",
                "properties": {{"name": {{"type": "string"}}}},
                "required": ["name"],
            }},
        }},
    ]


def call_tool(params: dict) -> dict:
    name = params.get("name")
    arguments = params.get("arguments") or {{}}
    if name == "describe_service":
        data = mcp_server_metadata()
    elif name == "create_demo_item":
        data = create_demo_item(str(arguments.get("name") or "demo")).model_dump()
    else:
        return {{"content": [{{"type": "text", "text": f"Unknown tool: {{name}}"}}], "isError": True}}
    return {{"content": [{{"type": "text", "text": str(data)}}]}}


def mcp_server_metadata() -> dict:
    return {{
        "name": settings.mcp_server_name,
        "transport": settings.mcp_server_transport,
        "endpoint": settings.mcp_server_endpoint,
        "tools": [
            {{
                "name": "describe_service",
                "description": "Return service metadata for agent discovery.",
            }},
            {{
                "name": "create_demo_item",
                "description": "Create a demo domain item from a name.",
            }},
        ],
    }}


def call_demo_tool(name: str) -> dict:
    return create_demo_item(name).model_dump()


def _error(request_id, code: int, message: str) -> dict:
    return {{"jsonrpc": "2.0", "id": request_id, "error": {{"code": code, "message": message}}}}
"""


def node_mcp_server(context: dict[str, object]) -> str:
    return """import { createItem } from '../../application/useCases.js';
import { settings } from '../../config/settings.js';

export function handleMcpRequest(payload: Record<string, any>) {
  const method = payload.method;
  const id = payload.id;
  if (method === 'initialize') {
    return { jsonrpc: '2.0', id, result: { protocolVersion: '2025-06-18', serverInfo: { name: settings.mcpServerName, version: '0.1.0' }, capabilities: { tools: {} } } };
  }
  if (method === 'tools/list') {
    return { jsonrpc: '2.0', id, result: { tools: mcpTools() } };
  }
  if (method === 'tools/call') {
    return { jsonrpc: '2.0', id, result: callTool(payload.params || {}) };
  }
  if (method === 'notifications/initialized') {
    return { jsonrpc: '2.0', id, result: null };
  }
  return { jsonrpc: '2.0', id, error: { code: -32601, message: `Unsupported MCP method: ${method}` } };
}

function mcpTools() {
  return [
    { name: 'describe_service', description: 'Return service metadata for agent discovery.', inputSchema: { type: 'object', properties: {} } },
    { name: 'create_demo_item', description: 'Create a demo domain item from a name.', inputSchema: { type: 'object', properties: { name: { type: 'string' } }, required: ['name'] } },
  ];
}

function callTool(params: Record<string, any>) {
  if (params.name === 'describe_service') return { content: [{ type: 'text', text: JSON.stringify(mcpServerMetadata()) }] };
  if (params.name === 'create_demo_item') return { content: [{ type: 'text', text: JSON.stringify(createItem(String(params.arguments?.name || 'demo'))) }] };
  return { content: [{ type: 'text', text: `Unknown tool: ${params.name}` }], isError: true };
}

export function mcpServerMetadata() {
  return {
    name: settings.mcpServerName,
    transport: settings.mcpServerTransport,
    endpoint: settings.mcpServerEndpoint,
    tools: [
      { name: 'describe_service', description: 'Return service metadata for agent discovery.' },
      { name: 'create_demo_item', description: 'Create a demo domain item from a name.' },
    ],
  };
}

export const callDemoTool = (name: string) => createItem(name);
"""


def java_mcp_controller(context: dict[str, object]) -> str:
    return """package com.example.interfaces;

import com.example.application.DemoService;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

@RestController
public class McpServerController {
  private final DemoService demoService;

  public McpServerController(DemoService demoService) {
    this.demoService = demoService;
  }

  @GetMapping("/mcp")
  public Object metadata() {
    return metadataResult();
  }

  @PostMapping("/mcp")
  public ResponseEntity<Object> mcp(
      @RequestBody Map<String, Object> payload,
      @RequestHeader(value = "Authorization", defaultValue = "") String authorization,
      @RequestHeader(value = "Origin", defaultValue = "") String origin,
      @RequestHeader(value = "Host", defaultValue = "") String host) {
    if (!authorized(authorization)) {
      return ResponseEntity.status(401).body(Map.of("detail", "Invalid MCP API key"));
    }
    if (!allowed(origin, System.getenv().getOrDefault("MCP_ALLOWED_ORIGINS", ""))) {
      return ResponseEntity.status(403).body(Map.of("detail", "Origin is not allowed"));
    }
    if (!allowed(host, System.getenv().getOrDefault("MCP_ALLOWED_HOSTS", ""))) {
      return ResponseEntity.status(403).body(Map.of("detail", "Host is not allowed"));
    }
    Object id = payload.get("id");
    String method = String.valueOf(payload.get("method"));
    if ("initialize".equals(method)) {
      return ResponseEntity.ok(response(id, Map.of(
        "protocolVersion", "2025-06-18",
        "serverInfo", Map.of("name", System.getenv().getOrDefault("MCP_SERVER_NAME", "demo-mcp"), "version", "0.1.0"),
        "capabilities", Map.of("tools", Map.of())
      )));
    }
    if ("tools/list".equals(method)) {
      return ResponseEntity.ok(response(id, Map.of("tools", List.of(
        Map.of("name", "describe_service", "description", "Return service metadata for agent discovery.", "inputSchema", Map.of("type", "object", "properties", Map.of())),
        Map.of("name", "create_demo_item", "description", "Create a demo domain item from a name.", "inputSchema", Map.of("type", "object", "properties", Map.of("name", Map.of("type", "string")), "required", List.of("name")))
      ))));
    }
    if ("tools/call".equals(method)) {
      return ResponseEntity.ok(response(id, Map.of("content", List.of(Map.of("type", "text", "text", metadataResult().toString())))));
    }
    if ("notifications/initialized".equals(method)) {
      return ResponseEntity.ok(response(id, null));
    }
    return ResponseEntity.ok(Map.of("jsonrpc", "2.0", "id", id, "error", Map.of("code", -32601, "message", "Unsupported MCP method: " + method)));
  }

  private Object response(Object id, Object result) {
    Map<String, Object> response = new LinkedHashMap<>();
    response.put("jsonrpc", "2.0");
    response.put("id", id);
    response.put("result", result);
    return response;
  }

  private Object metadataResult() {
    return Map.of(
      "name", System.getenv().getOrDefault("MCP_SERVER_NAME", "demo-mcp"),
      "transport", System.getenv().getOrDefault("MCP_SERVER_TRANSPORT", "streamable-http"),
      "endpoint", System.getenv().getOrDefault("MCP_SERVER_ENDPOINT", "/mcp"),
      "tools", List.of("describe_service", "create_demo_item")
    );
  }

  private boolean authorized(String authorization) {
    String apiKey = System.getenv().getOrDefault("MCP_API_KEY", "__REPLACE_WITH_MCP_API_KEY__");
    return apiKey.isBlank() || authorization.equals("Bearer " + apiKey);
  }

  private boolean allowed(String value, String csvValues) {
    if (csvValues.isBlank() || value.isBlank()) {
      return true;
    }
    return List.of(csvValues.split(",")).stream().map(String::trim).anyMatch(value::equals);
  }
}
"""
