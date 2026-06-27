param(
  [string]$Registry,
  [string]$Repository = "platform",
  [string]$Tag = "latest",
  [string]$OutputDir = "deploy/generated",
  [string]$HttpPort = "5186"
)

$ErrorActionPreference = "Stop"
if (-not $Registry) {
  throw "Registry is required, for example: -Registry registry.example.com"
}

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$TargetDir = $OutputDir
if (-not [System.IO.Path]::IsPathRooted($TargetDir)) {
  $TargetDir = Join-Path $RepoRoot $OutputDir
}
New-Item -ItemType Directory -Force -Path $TargetDir | Out-Null

$Prefix = $Registry.TrimEnd("/")
if ($Repository) {
  $Prefix = "$Prefix/$($Repository.Trim('/'))"
}

$BackendImage = "$Prefix/deployment-package-factory-backend:$Tag"
$WorkerImage = "$Prefix/deployment-package-factory-worker:$Tag"
$FrontendImage = "$Prefix/deployment-package-factory-frontend:$Tag"

$ComposeEnv = @"
DPF_BACKEND_IMAGE=$BackendImage
DPF_WORKER_IMAGE=$WorkerImage
DPF_FRONTEND_IMAGE=$FrontendImage
DPF_HTTP_PORT=$HttpPort
"@
$ComposeEnv | Set-Content -Encoding utf8 -NoNewline -LiteralPath (Join-Path $TargetDir "factory.env")

$Kustomization = @"
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - ../k8s
images:
  - name: deployment-package-factory-backend
    newName: $Prefix/deployment-package-factory-backend
    newTag: $Tag
  - name: deployment-package-factory-worker
    newName: $Prefix/deployment-package-factory-worker
    newTag: $Tag
  - name: deployment-package-factory-frontend
    newName: $Prefix/deployment-package-factory-frontend
    newTag: $Tag
"@
$Kustomization | Set-Content -Encoding utf8 -NoNewline -LiteralPath (Join-Path $TargetDir "kustomization.yaml")

Write-Host "Generated deployment image files:"
Write-Host "  $(Join-Path $TargetDir 'factory.env')"
Write-Host "  $(Join-Path $TargetDir 'kustomization.yaml')"
