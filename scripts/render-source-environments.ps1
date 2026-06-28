$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Resolve-Path (Join-Path $ScriptDir "..")

python (Join-Path $ScriptDir "render_source_environments.py") `
  --config (Join-Path $RepoRoot "deploy/source-environments/source-environments.yaml") `
  --output-dir (Join-Path $RepoRoot "deploy/source-environments")
