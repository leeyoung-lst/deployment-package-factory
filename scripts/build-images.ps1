param(
  [string]$Registry = "",
  [string]$Repository = "platform",
  [string]$Tag = "latest",
  [switch]$NoCache
)

$ErrorActionPreference = "Stop"
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$Prefix = ""
if ($Registry) {
  $Prefix = $Registry.TrimEnd("/")
  if ($Repository) {
    $Prefix = "$Prefix/$($Repository.Trim('/'))"
  }
}

function Image-Name([string]$Name) {
  if ($Prefix) {
    return "$Prefix/$Name`:$Tag"
  }
  return "$Name`:$Tag"
}

$BackendImage = Image-Name "deployment-package-factory-backend"
$WorkerImage = Image-Name "deployment-package-factory-worker"
$FrontendImage = Image-Name "deployment-package-factory-frontend"
$BuildArgs = @()
if ($NoCache) {
  $BuildArgs += "--no-cache"
}
if ($env:BUILD_PROXY_URL) {
  $BuildArgs += @("--build-arg", "HTTP_PROXY=$env:BUILD_PROXY_URL")
  $BuildArgs += @("--build-arg", "HTTPS_PROXY=$env:BUILD_PROXY_URL")
  $BuildArgs += @("--build-arg", "http_proxy=$env:BUILD_PROXY_URL")
  $BuildArgs += @("--build-arg", "https_proxy=$env:BUILD_PROXY_URL")
}
if ($env:BUILD_NO_PROXY_LIST) {
  $BuildArgs += @("--build-arg", "NO_PROXY=$env:BUILD_NO_PROXY_LIST")
  $BuildArgs += @("--build-arg", "no_proxy=$env:BUILD_NO_PROXY_LIST")
}
if ($env:BUILD_APT_MIRROR) {
  $BuildArgs += @("--build-arg", "APT_MIRROR=$env:BUILD_APT_MIRROR")
}
if ($env:BUILD_APT_SECURITY_MIRROR) {
  $BuildArgs += @("--build-arg", "APT_SECURITY_MIRROR=$env:BUILD_APT_SECURITY_MIRROR")
}
if ($env:BUILD_PIP_INDEX_URL) {
  $BuildArgs += @("--build-arg", "PIP_INDEX_URL=$env:BUILD_PIP_INDEX_URL")
}
if ($env:BUILD_NPM_REGISTRY) {
  $BuildArgs += @("--build-arg", "NPM_REGISTRY=$env:BUILD_NPM_REGISTRY")
}

Write-Host "Building $BackendImage"
docker build @BuildArgs -f "$RepoRoot/backend/Dockerfile" -t $BackendImage $RepoRoot

Write-Host "Building $WorkerImage"
docker build @BuildArgs -f "$RepoRoot/backend/Dockerfile.worker" -t $WorkerImage $RepoRoot

Write-Host "Building $FrontendImage"
docker build @BuildArgs -f "$RepoRoot/frontend/Dockerfile" -t $FrontendImage $RepoRoot

Write-Host "Built images:"
Write-Host "  $BackendImage"
Write-Host "  $WorkerImage"
Write-Host "  $FrontendImage"
