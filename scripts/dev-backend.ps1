Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location (Join-Path $root "backend")
uvicorn deployment_package_factory.main:app --reload --port 8096
