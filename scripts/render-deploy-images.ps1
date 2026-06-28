param(
  [string]$Registry,
  [string]$Repository = "platform",
  [string]$Tag = "latest",
  [string]$OutputDir = "deploy/generated",
  [string]$HttpPort = "5186",
  [string]$DatabaseUrl = "",
  [string]$StorageClass = ""
)

$ErrorActionPreference = "Stop"
if (-not $Registry) {
  throw "Registry is required, for example: -Registry registry.example.com"
}
if (-not $StorageClass) {
  throw "StorageClass is required for Kubernetes deployment config, for example: -StorageClass nfs-rwx"
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
DEPLOYMENT_PACKAGE_DATABASE_URL=$DatabaseUrl
"@
$ComposeEnv | Set-Content -Encoding utf8 -NoNewline -LiteralPath (Join-Path $TargetDir "factory.env")

$Kustomization = @"
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - ../k8s
patches:
  - path: pvc-storage-class-patch.yaml
  - path: worker-helper-image-patch.yaml
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

$PvcPatch = @"
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: deployment-package-factory-data
  namespace: deployment-package-factory
spec:
  storageClassName: $StorageClass
"@
$PvcPatch | Set-Content -Encoding utf8 -NoNewline -LiteralPath (Join-Path $TargetDir "pvc-storage-class-patch.yaml")

$WorkerPatch = @"
apiVersion: apps/v1
kind: Deployment
metadata:
  name: deployment-package-factory-worker
  namespace: deployment-package-factory
spec:
  template:
    spec:
      containers:
        - name: worker
          env:
            - name: DEPLOYMENT_PACKAGE_IMAGE_EXPORT_HELPER_IMAGE
              value: $WorkerImage
            - name: DEPLOYMENT_PACKAGE_NAMESPACE
              valueFrom:
                fieldRef:
                  fieldPath: metadata.namespace
"@
$WorkerPatch | Set-Content -Encoding utf8 -NoNewline -LiteralPath (Join-Path $TargetDir "worker-helper-image-patch.yaml")

Write-Host "Generated deployment image files:"
Write-Host "  $(Join-Path $TargetDir 'factory.env')"
Write-Host "  $(Join-Path $TargetDir 'kustomization.yaml')"
Write-Host "  $(Join-Path $TargetDir 'pvc-storage-class-patch.yaml')"
Write-Host "  $(Join-Path $TargetDir 'worker-helper-image-patch.yaml')"
