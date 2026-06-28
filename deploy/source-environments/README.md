# Source Environment Namespace Structure

This directory defines the source Kubernetes environments that the deployment package factory scans and exports from.

The namespace contract is:

```text
{env}-middleware-public
{env}-base-public
{env}-biz-{product}-{profile}
```

Initial environments:

```text
dev-middleware-public
dev-base-public
dev-biz-eam-4x60
dev-biz-mes-4x60
dev-biz-mes-4x3

test-middleware-public
test-base-public
test-biz-eam-4x60
test-biz-mes-4x60
test-biz-mes-4x3
```

Render manifests:

```bash
scripts/render-source-environments.sh
```

Install namespaces:

```bash
scripts/install-source-environments.sh
```

Windows PowerShell:

```powershell
.\scripts\render-source-environments.ps1
.\scripts\install-source-environments.ps1
```

The first step only creates and labels namespaces. NetworkPolicy rollout is intentionally kept out of the default kustomization so existing workloads are not cut off before the Pod/container classifier is enabled.

Classifier labels:

```text
local-ai.io/environment=dev|test
local-ai.io/layer=middleware|base-platform|business
local-ai.io/product=eam|mes
local-ai.io/profile=4x60|4x3
deployment-package-factory.local-ai/status=active
```
