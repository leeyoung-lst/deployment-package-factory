$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Resolve-Path (Join-Path $ScriptDir "..")

& (Join-Path $ScriptDir "render-source-environments.ps1")
kubectl apply -k (Join-Path $RepoRoot "deploy/source-environments")
