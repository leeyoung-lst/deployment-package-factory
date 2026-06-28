param(
  [ValidateSet("k8s", "docker-compose")]
  [string]$Mode = "k8s"
)

$ErrorActionPreference = "Stop"
$RootDir = Resolve-Path (Join-Path $PSScriptRoot "..")

function Fail([string]$Message) {
  throw "Deployment config validation failed: $Message"
}

function Require-File([string]$RelativePath) {
  $path = Join-Path $RootDir $RelativePath
  if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
    Fail "missing required file: $RelativePath"
  }
}

function Reject-Placeholders([string]$RelativePath) {
  $path = Join-Path $RootDir $RelativePath
  $content = Get-Content -LiteralPath $path -Raw
  if ($content -match "__REPLACE_WITH_") {
    Fail "placeholder remains in $RelativePath"
  }
}

if ($Mode -eq "k8s") {
  Require-File "deploy/k8s/pvc.yaml"
  Require-File "deploy/k8s/secret.yaml"
  Require-File "deploy/k8s/kustomization.yaml"
  Require-File "deploy/generated/kustomization.yaml"
  Require-File "deploy/generated/pvc-storage-class-patch.yaml"
  Reject-Placeholders "deploy/k8s/secret.yaml"
  Reject-Placeholders "deploy/generated/pvc-storage-class-patch.yaml"
  $kustomization = Get-Content -LiteralPath (Join-Path $RootDir "deploy/k8s/kustomization.yaml") -Raw
  if ($kustomization -notmatch "- secret\.yaml") {
    Fail "deploy/k8s/kustomization.yaml must include deploy/k8s/secret.yaml"
  }
  $generatedKustomization = Get-Content -LiteralPath (Join-Path $RootDir "deploy/generated/kustomization.yaml") -Raw
  if ($generatedKustomization -notmatch "pvc-storage-class-patch\.yaml") {
    Fail "deploy/generated/kustomization.yaml must include pvc-storage-class-patch.yaml"
  }
  $pvc = Get-Content -LiteralPath (Join-Path $RootDir "deploy/k8s/pvc.yaml") -Raw
  if ($pvc -notmatch "ReadWriteMany") {
    Fail "deploy/k8s/pvc.yaml must use ReadWriteMany for shared artifact storage"
  }
  $pvcPatch = Get-Content -LiteralPath (Join-Path $RootDir "deploy/generated/pvc-storage-class-patch.yaml") -Raw
  if ($pvcPatch -notmatch "storageClassName:\s*\S+") {
    Fail "deploy/generated/pvc-storage-class-patch.yaml must define storageClassName"
  }
  $secret = Get-Content -LiteralPath (Join-Path $RootDir "deploy/k8s/secret.yaml") -Raw
  if ($secret -notmatch "DEPLOYMENT_PACKAGE_DATABASE_URL") {
    Fail "deploy/k8s/secret.yaml must define DEPLOYMENT_PACKAGE_DATABASE_URL"
  }
} else {
  Require-File "deploy/generated/factory.env"
  $envFile = Get-Content -LiteralPath (Join-Path $RootDir "deploy/generated/factory.env") -Raw
  if ($envFile -notmatch "(?m)^DEPLOYMENT_PACKAGE_DATABASE_URL=") {
    Fail "deploy/generated/factory.env must define DEPLOYMENT_PACKAGE_DATABASE_URL for production compose"
  }
  Reject-Placeholders "deploy/generated/factory.env"
}

Write-Host "Deployment config validation passed for $Mode."
