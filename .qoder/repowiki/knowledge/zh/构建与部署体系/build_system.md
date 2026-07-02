## 1. 核心构建系统
项目采用 **Docker + Jenkins** 为核心的构建与交付体系，辅以 **Kustomize** 进行 Kubernetes 配置管理。

- **后端 (Backend)**: 基于 `Python 3.12`，使用 `hatchling` 作为构建后端。通过 `backend/Dockerfile` 和 `backend/Dockerfile.worker` 分别构建 API 服务和异步 Worker 镜像。镜像内预装 `skopeo` 等工具以支持容器镜像操作。
- **前端 (Frontend)**: 基于 `Node.js 22` 和 `pnpm` 包管理器，使用 `Vite` 进行构建。采用多阶段构建（Multi-stage build），最终产物托管于 `nginx:1.27-alpine`。
- **依赖管理**: 
  - Python: `pyproject.toml` 定义依赖，生产环境通过 `pip install .` 安装。
  - Node.js: `package.json` 配合 `pnpm-lock.yaml` 确保依赖一致性。

## 2. CI/CD 流水线 (Jenkins)
根目录下的 `Jenkinsfile` 定义了完整的自动化流水线：

1.  **Prepare**: 确定镜像标签（默认使用 Git Commit SHA）。
2.  **Build Images**: 调用 `scripts/build-images.sh` 并行构建 Backend、Worker 和 Frontend 镜像。支持传入国内镜像源（如阿里云 PyPI/NPM）以加速构建。
3.  **Push Images**: 将构建好的镜像推送到指定的 Harbor 仓库。
4.  **Render Deploy Config**: 使用 `scripts/render-deploy-images.sh` 生成针对特定环境的 Kustomize 补丁文件（如 StorageClass、镜像地址）。
5.  **Deploy to K8s**: 通过 `kubectl apply -k deploy/generated` 将应用部署到 Kubernetes 集群。
6.  **Smoke Test**: 执行健康检查接口 (`/health/ready`) 和业务接口连通性测试。

## 3. 部署架构与配置
- **本地开发**: 使用根目录的 `docker-compose.yml` 快速启动前后端服务。
- **生产部署**: 
  - **Kubernetes**: 位于 `deploy/k8s/`，包含 Namespace、RBAC、PVC、Deployment 等标准清单。通过 `deploy/generated/` 下的动态生成文件实现环境差异化配置。
  - **Docker Compose**: 提供 `deploy/docker-compose.prod.yml` 用于非 K8s 环境的生产级部署，支持持久化卷和网络隔离。

## 4. 开发者规范
- **镜像构建**: 严禁直接运行 `docker build`，应统一使用 `scripts/build-images.sh` 脚本，以确保构建参数（如代理、镜像源）的一致性。
- **配置渲染**: 修改 K8s 部署配置时，应更新 `deploy/k8s/` 下的模板文件，并通过渲染脚本生成最终配置，避免手动修改 `deploy/generated/` 下的文件。
- **版本控制**: 镜像标签建议遵循语义化版本或使用 Git SHA，确保构建产物可追溯。