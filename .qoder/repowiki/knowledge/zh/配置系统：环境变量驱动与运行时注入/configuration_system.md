## 1. 核心架构与模式
该项目的配置系统采用**环境变量驱动（Environment-Driven）**的架构，遵循 Twelve-Factor App 原则。配置分为后端服务配置、前端运行时配置以及基础设施部署配置三个层面。

- **后端 (Python/FastAPI)**: 使用自定义的 `dataclass` 配合 `os.getenv` 实现配置的加载与类型转换。不依赖第三方配置库（如 Pydantic Settings），保持轻量级。
- **前端 (React/Vite)**: 采用**运行时配置注入**模式。通过 `public/runtime-config.js` 文件在容器启动时动态覆盖 API 地址和 Token，避免了前端代码的重构建。
- **部署层 (K8s/Docker)**: 利用 Kubernetes ConfigMap/Secret 和 Docker Compose 的环境变量映射来管理不同环境的配置差异。

## 2. 关键文件与职责

### 后端配置
- `backend/deployment_package_factory/settings.py`: 核心配置模块。定义了 `DeploymentPackageSettings` 数据类，并通过 `load_settings()` 函数从环境变量中读取配置。支持默认值回退和简单的类型校验（如正整数检查）。
- `backend/pyproject.toml`: 定义项目依赖，但未包含专门的配置管理库。

### 前端配置
- `frontend/public/runtime-config.js`: 运行时配置入口。定义了全局对象 `window.__DEPLOYMENT_PACKAGE_FACTORY_CONFIG__`，用于在浏览器环境中存储 API 基础路径和认证 Token。
- `frontend/src/api/client.ts`: 配置消费端。优先读取运行时配置（`runtime-config.js`），其次回退到 Vite 的编译时环境变量（`import.meta.env`）。

### 部署配置
- `deploy/k8s/configmap.yaml`: 定义后端服务的非敏感配置，如数据目录路径、并发构建数、保留策略等。
- `deploy/k8s/secret.template.yaml`: 定义敏感信息模板，包括数据库连接串、API Token 和镜像仓库凭证。
- `docker-compose.yml`: 本地或简单部署时的环境变量映射，支持通过 `.env` 文件或 shell 环境变量注入。

## 3. 配置分层与优先级

### 后端配置优先级
1. **环境变量**: 所有以 `DEPLOYMENT_PACKAGE_` 为前缀的环境变量具有最高优先级。
2. **代码默认值**: 当环境变量缺失时，使用 `settings.py` 中定义的硬编码默认值（如 `DEFAULT_DATA_DIR`）。

### 前端配置优先级
1. **运行时配置 (`runtime-config.js`)**: 部署后通过脚本修改此文件可立即生效，无需重新打包。
2. **编译时环境变量 (`.env` / Vite Env)**: 仅在构建阶段生效，作为运行时配置的后备。

## 4. 开发者规范与约束

- **命名约定**: 所有环境变量必须使用 `DEPLOYMENT_PACKAGE_` 前缀，以保持命名空间隔离。
- **敏感信息管理**: 
  - 严禁将 `DEPLOYMENT_PACKAGE_API_TOKEN` 或数据库密码硬编码在代码中。
  - 生产环境必须使用 Kubernetes Secrets 或 Docker Secrets 管理敏感数据。
- **前端配置更新**: 若需更改前端连接的 API 地址，应修改 `public/runtime-config.js` 或通过 Nginx 挂载该文件，而不是修改 Vite 配置文件后重新构建镜像。
- **类型安全**: 后端配置加载时已包含基本的类型转换逻辑（如 `_positive_int`），新增配置项时应遵循此模式，确保配置值的合法性。