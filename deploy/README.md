# Deployment Package Factory 部署说明

本目录用于部署“部署包工厂”自身，而不是它生成的业务生产部署包。

## 镜像

默认镜像名：

```text
deployment-package-factory-backend:latest
deployment-package-factory-frontend:latest
```

构建示例：

```bash
scripts/build-images.sh --tag latest
```

Windows PowerShell：

```powershell
.\scripts\build-images.ps1 -Tag latest
```

构建并推送到镜像仓库：

```bash
scripts/build-images.sh --registry registry.example.com --repository platform --tag 2026.06
scripts/push-images.sh --registry registry.example.com --repository platform --tag 2026.06
```

Windows PowerShell：

```powershell
.\scripts\build-images.ps1 -Registry registry.example.com -Repository platform -Tag 2026.06
.\scripts\push-images.ps1 -Registry registry.example.com -Repository platform -Tag 2026.06
```

推送后，替换 `deploy/k8s/backend.yaml` 和 `deploy/k8s/frontend.yaml` 中的 `image`，或在 Docker Compose 中设置 `DPF_BACKEND_IMAGE` 和 `DPF_FRONTEND_IMAGE`。

也可以生成部署镜像配置文件：

```bash
scripts/render-deploy-images.sh --registry registry.example.com --repository platform --tag 2026.06
```

Windows PowerShell：

```powershell
.\scripts\render-deploy-images.ps1 -Registry registry.example.com -Repository platform -Tag 2026.06
```

默认会生成：

```text
deploy/generated/factory.env
deploy/generated/kustomization.yaml
```

## Docker Compose

```bash
docker compose --env-file deploy/generated/factory.env -f deploy/docker-compose.prod.yml up -d
```

可选环境变量：

```bash
export DPF_BACKEND_IMAGE=registry.example.com/platform/deployment-package-factory-backend:2026.06
export DPF_FRONTEND_IMAGE=registry.example.com/platform/deployment-package-factory-frontend:2026.06
export DPF_HTTP_PORT=5186
export DEPLOYMENT_PACKAGE_MAX_CONCURRENT_BUILDS=1
export DEPLOYMENT_PACKAGE_RETENTION_DAYS=30
export DEPLOYMENT_PACKAGE_MAX_TOTAL_GB=500
```

访问：

```text
http://localhost:5186
```

数据会写入 Docker volume `deployment-package-data`。

## Kubernetes

部署：

```bash
kubectl apply -k deploy/generated
```

部署后检查：

```bash
kubectl get pods -n deployment-package-factory
kubectl get ingress -n deployment-package-factory
```

默认域名：

```text
deployment-package-factory.example.com
```

生产使用前需要调整：

- `deploy/k8s/ingress.yaml` 中的域名。
- `scripts/render-deploy-images.*` 生成的镜像地址。
- `deploy/k8s/pvc.yaml` 中的存储大小和 StorageClass。
- `deploy/k8s/configmap.yaml` 中的并发数、保留天数和容量上限。

## 数据与权限

后端需要持久化以下内容：

```text
/app/data/deployment-package-tasks.sqlite3
/app/data/deployment-packages/
```

如果启用镜像归档导出，运行后端的节点还需要可访问来源镜像仓库，并具备 Docker CLI 或后续 worker 镜像导出能力。当前 K8s 清单默认用于镜像清单模式和配置包生成，不挂载宿主机 Docker socket。
