# Deployment Package Factory

独立部署包导出项目，用于从开发环境或测试环境选择基础平台能力、业务产品和中间件依赖，生成生产交付包。

## 项目结构

- `backend/`: 独立 FastAPI 服务，提供能力目录、依赖预览、部署包生成和下载接口。
- `frontend/`: 独立 Vite + React 页面，面向实施人员执行导包。
- `templates/catalog/`: 基础平台、业务产品、中间件和依赖规则目录。
- `data/deployment-packages/`: 默认部署包输出目录，运行时生成。

## 本地运行

后端：

```powershell
cd deployment-package-factory/backend
uvicorn deployment_package_factory.main:app --reload --port 8096
```

前端：

```powershell
cd deployment-package-factory/frontend
pnpm install
pnpm dev
```

前端开发服务默认代理 `/api` 到 `http://127.0.0.1:8096`。

也可以直接启动容器化版本：

```powershell
cd deployment-package-factory
docker compose up --build
```

访问 `http://127.0.0.1:5186`。

## 当前能力

- 支持 `dev`、`test` 来源环境。
- 支持 `k8s`、`docker-compose` 部署方式选择。
- 基础平台能力包括 IAM、AI / Agent、File / Documents、Workflow / Camunda、Audit、Gateway / Frontend Shell。
- 业务产品包括 EAM、MES、ERP、APS。
- 数据库在达梦 DM 与 PostgreSQL 中二选一。
- 中间件依赖按所选基础能力和业务产品自动解析。
- 生成包包含 manifest、安装文档、K8s namespace、Docker Compose 样例、初始化脚本占位和安全摘要。

## 后续硬化

- 接入实际镜像仓库导出 `docker save` 或 OCI archive。
- 将内存任务记录替换为 SQLite/PostgreSQL 任务表。
- 按项目模板扩展 Helm/Kustomize 与 Compose 渲染器。
- 增加离线安装校验、镜像 digest 锁定和初始化 SQL 分层。
