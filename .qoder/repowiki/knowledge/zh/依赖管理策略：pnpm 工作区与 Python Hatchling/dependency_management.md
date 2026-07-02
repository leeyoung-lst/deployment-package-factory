该项目采用前后端分离的依赖管理体系，前端使用 **pnpm** 进行包管理与工作区（Workspace）配置，后端使用 **Python (pip/hatchling)** 进行依赖声明。

### 1. 前端依赖管理 (Frontend)
- **包管理器**: 使用 `pnpm@10.24.0`，通过 `package.json` 中的 `packageManager` 字段锁定版本，并利用 `corepack` 在构建时激活。
- **工作区配置**: 根目录下的 `pnpm-workspace.yaml` 定义了 `frontend` 为唯一的工作区成员，并显式允许 `esbuild` 的二进制构建。
- **锁定文件**: 使用 `pnpm-lock.yaml` (lockfileVersion: '9.0') 确保依赖版本的确定性。在 Docker 构建中，通过 `pnpm install --frozen-lockfile` 强制使用锁定文件，防止意外更新。
- **私有源支持**: `frontend/Dockerfile` 支持通过 `NPM_REGISTRY` 构建参数动态配置 npm 镜像源，适应内网或加速需求。

### 2. 后端依赖管理 (Backend)
- **构建系统**: 采用现代化的 `pyproject.toml` 标准，指定 `hatchling` 作为构建后端 (`build-backend = "hatchling.build"`)。
- **依赖声明**: 在 `[project.dependencies]` 中声明核心依赖（如 `fastapi`, `uvicorn`, `pydantic`），在 `[project.optional-dependencies]` 中声明开发依赖（如 `pytest`, `httpx`）。
- **版本约束**: 严格限制 Python 版本为 `>=3.12,<3.13`，确保运行环境的一致性。
- **安装方式**: 在 `backend/Dockerfile` 中，通过 `pip install --no-cache-dir .` 直接安装当前目录下的项目及其依赖。
- **私有源支持**: 支持通过 `PIP_INDEX_URL` 环境变量配置 pip 索引地址，便于在内网环境中拉取第三方库。

### 3. 开发者规范
- **前端**: 严禁手动修改 `pnpm-lock.yaml`，应始终通过 `pnpm add/remove` 命令管理依赖。提交代码前需确保 `pnpm install` 能成功执行且无锁文件冲突。
- **后端**: 新增依赖需同步更新 `pyproject.toml`。由于未提供 `requirements.txt` 或 `poetry.lock`，建议团队统一使用 `pip` 配合 `pyproject.toml` 进行环境复现。
- **构建一致性**: CI/CD 流程中应利用 Docker 构建参数注入内部镜像源地址，确保在不同网络环境下构建的稳定性和速度。