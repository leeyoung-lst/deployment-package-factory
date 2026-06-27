param(
  [string]$Registry,
  [string]$Repository = "platform",
  [string]$Tag = "latest"
)

$ErrorActionPreference = "Stop"
if (-not $Registry) {
  throw "Registry is required, for example: -Registry registry.example.com"
}

$Prefix = $Registry.TrimEnd("/")
if ($Repository) {
  $Prefix = "$Prefix/$($Repository.Trim('/'))"
}

$Images = @(
  "$Prefix/deployment-package-factory-backend`:$Tag",
  "$Prefix/deployment-package-factory-worker`:$Tag",
  "$Prefix/deployment-package-factory-frontend`:$Tag"
)

foreach ($Image in $Images) {
  Write-Host "Pushing $Image"
  docker push $Image
}

Write-Host "Pushed images:"
$Images | ForEach-Object { Write-Host "  $_" }
