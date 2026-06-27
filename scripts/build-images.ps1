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
