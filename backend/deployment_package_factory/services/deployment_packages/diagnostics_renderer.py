from __future__ import annotations

from pathlib import PurePosixPath


def render_diagnostics_files(manifest: dict, services: list[dict], middleware_keys: list[str]) -> list[tuple[PurePosixPath, str, bool]]:
    return [
        (PurePosixPath("scripts/diagnostics.sh"), _diagnostics_sh(manifest, services, middleware_keys), True),
        (PurePosixPath("scripts/diagnostics.ps1"), _diagnostics_ps1(manifest, services, middleware_keys), False),
    ]


def _diagnostics_sh(manifest: dict, services: list[dict], middleware_keys: list[str]) -> str:
    namespaces = " ".join(_namespaces(manifest, services))
    middleware_tcp = " ".join(f"{key}:127.0.0.1:{_middleware_port(key, manifest)}" for key in middleware_keys)
    app_tcp = " ".join(f"{item['name']}:127.0.0.1:{item['hostPort']}" for item in services)
    app_http = " ".join(_http_check_value(item) for item in services if _http_check_value(item))
    endpoints = " ".join(f"{namespace}:{name}" for namespace, name in _k8s_endpoint_checks(manifest, services, middleware_keys))
    return (
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        'MODE="${1:-k8s}"\n'
        f'NAMESPACES="{namespaces}"\n'
        f'COMPOSE_MIDDLEWARE_TCP_CHECKS="{middleware_tcp}"\n'
        f'COMPOSE_APP_TCP_CHECKS="{app_tcp}"\n'
        f'COMPOSE_HTTP_CHECKS="{app_http}"\n'
        f'K8S_ENDPOINT_CHECKS="{endpoints}"\n'
        'SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"\n'
        'PACKAGE_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"\n'
        "\n"
        "fail() { echo \"Deployment diagnostics failed: $*\" >&2; exit 1; }\n"
        "require_command() { command -v \"$1\" >/dev/null 2>&1 || fail \"missing command: $1\"; }\n"
        "\n"
        "tcp_check() {\n"
        '  local name="$1" host="$2" port="$3"\n'
        '  if timeout 8 bash -c "cat < /dev/null > /dev/tcp/${host}/${port}" 2>/dev/null; then\n'
        '    echo "TCP check passed: ${name} ${host}:${port}"\n'
        "  else\n"
        '    fail "${name} is not reachable at ${host}:${port}"\n'
        "  fi\n"
        "}\n"
        "\n"
        "http_check() {\n"
        '  local name="$1" url="$2" fallback_host="$3" fallback_port="$4"\n'
        "  if command -v curl >/dev/null 2>&1; then\n"
        '    curl -fsS --max-time 10 "${url}" >/dev/null || fail "${name} HTTP check failed: ${url}"\n'
        "  elif command -v python3 >/dev/null 2>&1; then\n"
        '    URL="${url}" python3 - <<\'PY\' || exit 1\n'
        "import os\n"
        "import sys\n"
        "import urllib.request\n"
        "try:\n"
        "    with urllib.request.urlopen(os.environ['URL'], timeout=10) as response:\n"
        "        if response.status >= 400:\n"
        "            raise RuntimeError(f'status={response.status}')\n"
        "except Exception as exc:\n"
        "    print(f'HTTP check failed: {exc}', file=sys.stderr)\n"
        "    raise SystemExit(1)\n"
        "PY\n"
        "  else\n"
        '    tcp_check "${name}" "${fallback_host}" "${fallback_port}"\n'
        "  fi\n"
        '  echo "HTTP check passed: ${name} ${url}"\n'
        "}\n"
        "\n"
        "docker_compose_diagnostics() {\n"
        "  require_command docker\n"
        '  local compose_file="${PACKAGE_ROOT}/docker-compose/docker-compose.yml"\n'
        '  local env_file="${PACKAGE_ROOT}/docker-compose/.env"\n'
        '  [ -f "${env_file}" ] || fail "docker-compose/.env not found"\n'
        '  mapfile -t containers < <(docker compose --env-file "${env_file}" -f "${compose_file}" ps -q)\n'
        '  [ "${#containers[@]}" -gt 0 ] || fail "no docker-compose containers are running"\n'
        '  for container in "${containers[@]}"; do\n'
        '    local name state restarts health\n'
        '    name="$(docker inspect -f "{{.Name}}" "${container}" | sed "s#^/##")"\n'
        '    state="$(docker inspect -f "{{.State.Status}}" "${container}")"\n'
        '    restarts="$(docker inspect -f "{{.RestartCount}}" "${container}")"\n'
        '    health="$(docker inspect -f "{{if .State.Health}}{{.State.Health.Status}}{{end}}" "${container}")"\n'
        '    [ "${state}" = "running" ] || fail "${name} state=${state}"\n'
        '    [ "${restarts}" = "0" ] || fail "${name} restart count=${restarts}"\n'
        '    [ -z "${health}" ] || [ "${health}" = "healthy" ] || fail "${name} health=${health}"\n'
        "  done\n"
        '  for item in ${COMPOSE_MIDDLEWARE_TCP_CHECKS} ${COMPOSE_APP_TCP_CHECKS}; do\n'
        '    IFS=":" read -r name host port <<< "${item}"\n'
        '    tcp_check "${name}" "${host}" "${port}"\n'
        "  done\n"
        '  for item in ${COMPOSE_HTTP_CHECKS}; do\n'
        '    IFS="|" read -r name url host port <<< "${item}"\n'
        '    http_check "${name}" "${url}" "${host}" "${port}"\n'
        "  done\n"
        '  echo "Docker Compose diagnostics passed."\n'
        "}\n"
        "\n"
        "k8s_diagnostics() {\n"
        "  require_command kubectl\n"
        "  for namespace in ${NAMESPACES}; do\n"
        '    kubectl wait --for=condition=Ready pod --all -n "${namespace}" --timeout=180s\n'
        "  done\n"
        "  for item in ${K8S_ENDPOINT_CHECKS}; do\n"
        '    IFS=":" read -r namespace service <<< "${item}"\n'
        '    addresses="$(kubectl -n "${namespace}" get endpoints "${service}" -o jsonpath="{.subsets[*].addresses[*].ip}" 2>/dev/null || true)"\n'
        '    [ -n "${addresses}" ] || fail "service ${namespace}/${service} has no ready endpoints"\n'
        '    echo "Endpoint check passed: ${namespace}/${service}"\n'
        "  done\n"
        '  echo "K8s diagnostics passed."\n'
        "}\n"
        "\n"
        'case "${MODE}" in\n'
        "  k8s) k8s_diagnostics ;;\n"
        "  docker-compose) docker_compose_diagnostics ;;\n"
        '  *) fail "unknown diagnostics mode: ${MODE}" ;;\n'
        "esac\n"
    )


def _diagnostics_ps1(manifest: dict, services: list[dict], middleware_keys: list[str]) -> str:
    namespaces = _ps_array(_namespaces(manifest, services))
    middleware_tcp = _ps_array(f"{key}|127.0.0.1|{_middleware_port(key, manifest)}" for key in middleware_keys)
    app_tcp = _ps_array(f"{item['name']}|127.0.0.1|{item['hostPort']}" for item in services)
    app_http = _ps_array(item for item in (_http_check_value(service) for service in services) if item)
    endpoints = _ps_array(f"{namespace}|{name}" for namespace, name in _k8s_endpoint_checks(manifest, services, middleware_keys))
    return (
        "param(\n"
        "  [ValidateSet('k8s', 'docker-compose')]\n"
        "  [string]$Mode = 'k8s'\n"
        ")\n"
        "$ErrorActionPreference = 'Stop'\n"
        f"$Namespaces = @({namespaces})\n"
        f"$ComposeMiddlewareTcpChecks = @({middleware_tcp})\n"
        f"$ComposeAppTcpChecks = @({app_tcp})\n"
        f"$ComposeHttpChecks = @({app_http})\n"
        f"$K8sEndpointChecks = @({endpoints})\n"
        "$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path\n"
        "$PackageRoot = Split-Path -Parent $ScriptDir\n"
        "\n"
        "function Fail([string]$Message) { throw \"Deployment diagnostics failed: $Message\" }\n"
        "function Require-Command([string]$Name) { if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) { Fail \"missing command: $Name\" } }\n"
        "function Test-TcpPort([string]$Name, [string]$HostName, [int]$Port) {\n"
        "  $client = [System.Net.Sockets.TcpClient]::new()\n"
        "  try {\n"
        "    $async = $client.BeginConnect($HostName, $Port, $null, $null)\n"
        "    if (-not $async.AsyncWaitHandle.WaitOne(8000)) { Fail \"$Name is not reachable at ${HostName}:$Port\" }\n"
        "    $client.EndConnect($async)\n"
        "    Write-Host \"TCP check passed: $Name ${HostName}:$Port\"\n"
        "  } finally { $client.Close() }\n"
        "}\n"
        "function Test-HttpEndpoint([string]$Name, [string]$Url, [string]$HostName, [int]$Port) {\n"
        "  try { $response = Invoke-WebRequest -UseBasicParsing -TimeoutSec 10 -Uri $Url }\n"
        "  catch { Fail \"$Name HTTP check failed: $Url ($($_.Exception.Message))\" }\n"
        "  if ([int]$response.StatusCode -ge 400) { Fail \"$Name HTTP status $($response.StatusCode): $Url\" }\n"
        "  Write-Host \"HTTP check passed: $Name $Url\"\n"
        "}\n"
        "function Invoke-DockerComposeDiagnostics {\n"
        "  Require-Command 'docker'\n"
        "  $composeFile = Join-Path $PackageRoot 'docker-compose/docker-compose.yml'\n"
        "  $envFile = Join-Path $PackageRoot 'docker-compose/.env'\n"
        "  if (-not (Test-Path -LiteralPath $envFile -PathType Leaf)) { Fail 'docker-compose/.env not found' }\n"
        "  $ids = @(& docker compose --env-file $envFile -f $composeFile ps -q)\n"
        "  if (-not $ids.Count) { Fail 'no docker-compose containers are running' }\n"
        "  foreach ($id in $ids) {\n"
        "    $state = & docker inspect -f '{{.State.Status}}' $id\n"
        "    $name = (& docker inspect -f '{{.Name}}' $id).TrimStart('/')\n"
        "    $restarts = [int](& docker inspect -f '{{.RestartCount}}' $id)\n"
        "    $health = & docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{end}}' $id\n"
        "    if ($state -ne 'running') { Fail \"$name state=$state\" }\n"
        "    if ($restarts -ne 0) { Fail \"$name restart count=$restarts\" }\n"
        "    if ($health -and $health -ne 'healthy') { Fail \"$name health=$health\" }\n"
        "  }\n"
        "  foreach ($item in @($ComposeMiddlewareTcpChecks + $ComposeAppTcpChecks)) {\n"
        "    $parts = $item -split '\\|'\n"
        "    Test-TcpPort $parts[0] $parts[1] ([int]$parts[2])\n"
        "  }\n"
        "  foreach ($item in $ComposeHttpChecks) {\n"
        "    $parts = $item -split '\\|'\n"
        "    Test-HttpEndpoint $parts[0] $parts[1] $parts[2] ([int]$parts[3])\n"
        "  }\n"
        "  Write-Host 'Docker Compose diagnostics passed.'\n"
        "}\n"
        "function Invoke-K8sDiagnostics {\n"
        "  Require-Command 'kubectl'\n"
        "  foreach ($namespace in $Namespaces) { & kubectl wait --for=condition=Ready pod --all -n $namespace --timeout=180s }\n"
        "  foreach ($item in $K8sEndpointChecks) {\n"
        "    $parts = $item -split '\\|'\n"
        "    $addresses = & kubectl -n $parts[0] get endpoints $parts[1] -o jsonpath='{.subsets[*].addresses[*].ip}' 2>$null\n"
        "    if (-not $addresses) { Fail \"service $($parts[0])/$($parts[1]) has no ready endpoints\" }\n"
        "    Write-Host \"Endpoint check passed: $($parts[0])/$($parts[1])\"\n"
        "  }\n"
        "  Write-Host 'K8s diagnostics passed.'\n"
        "}\n"
        "if ($Mode -eq 'k8s') { Invoke-K8sDiagnostics } else { Invoke-DockerComposeDiagnostics }\n"
    )


def _namespaces(manifest: dict, services: list[dict]) -> list[str]:
    return sorted({service["namespace"] for service in services} | {_middleware_namespace(manifest)})


def _k8s_endpoint_checks(manifest: dict, services: list[dict], middleware_keys: list[str]) -> list[tuple[str, str]]:
    checks = [(service["namespace"], service["name"]) for service in services]
    checks.extend((_middleware_namespace(manifest), key) for key in middleware_keys)
    return sorted(set(checks))


def _http_check_value(service: dict) -> str:
    name = service["name"]
    port = int(service["port"])
    host_port = int(service["hostPort"])
    if port == 80 or "frontend" in name or name.startswith("sub-app"):
        return f"{name}|http://127.0.0.1:{host_port}/|127.0.0.1|{host_port}"
    if port in {8000, 8020}:
        return f"{name}|http://127.0.0.1:{host_port}/health|127.0.0.1|{host_port}"
    return ""


def _middleware_port(key: str, manifest: dict) -> int:
    return int(((manifest.get("middlewareConfig") or {}).get(key) or {}).get("port") or 8080)


def _middleware_namespace(manifest: dict) -> str:
    return f"{manifest['targetProfile'].get('namespacePrefix') or 'prod'}-middleware"


def _ps_array(values) -> str:
    return ", ".join("'" + str(item).replace("'", "''") + "'" for item in values)
