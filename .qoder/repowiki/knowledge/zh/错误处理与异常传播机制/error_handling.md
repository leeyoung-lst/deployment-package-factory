该部署包工厂全栈平台采用基于 FastAPI 的标准化 HTTP 错误响应机制，结合领域自定义异常类与异步任务容错策略，实现了从 API 层到后台 Worker 的全链路错误处理。

### 1. 核心策略与模式
- **HTTP 异常映射**：在 API 路由层（`api/`），所有业务逻辑抛出的底层异常均被捕获并转换为 `fastapi.HTTPException`。这确保了前端接收到统一的 JSON 错误格式 `{"detail": "..."}`。
- **领域自定义异常**：服务层（`services/`）定义了特定的异常类（如 `PackageBuildError`, `CatalogError`, `KubernetesRuntimeError`），用于区分不同类型的故障（配置错误、构建失败、基础设施交互失败）。
- **异步任务容错**：后台 Worker (`worker.py`) 和任务执行器 (`task_executor.py`) 采用“捕获即记录”的策略。任何未预期的异常都会导致任务状态标记为 `failed`，而不会导致进程崩溃，保证了系统的稳定性。
- **静默审计失败**：审计日志记录操作被包裹在宽泛的 `try...except Exception` 中，确保审计功能的故障不会影响核心业务流程。

### 2. 关键文件与组件
- **`backend/deployment_package_factory/api/deployment_packages.py`**：展示了最完整的异常转换逻辑。例如，将 `CatalogError` 和 `ValueError` 映射为 `400 Bad Request`，将 `KeyError` 映射为 `404 Not Found`。
- **`backend/deployment_package_factory/services/deployment_packages/builder.py`**：定义了 `PackageBuildError(RuntimeError)`，在镜像导出、目录操作等重型任务失败时抛出。
- **`backend/deployment_package_factory/services/deployment_packages/catalog.py`**：定义了 `CatalogError(ValueError)`，用于处理 YAML 配置解析和校验错误。
- **`backend/deployment_package_factory/services/deployment_packages/kubernetes_runtime.py`**：定义了 `KubernetesRuntimeError(RuntimeError)`，封装了与 K8s API Server 交互时的网络或权限错误。
- **`backend/deployment_package_factory/services/deployment_packages/task_executor.py`**：实现了异步任务的统一异常捕获，区分了预期错误（`CatalogError`）和意外错误（`Exception`）。

### 3. 架构约定与规则
- **状态码映射规范**：
  - `400 Bad Request`：用于参数校验失败、配置冲突或业务逻辑违规（如 `ValueError`, `CatalogError`）。
  - `404 Not Found`：用于资源不存在（如 `KeyError` 查找任务或微服务注册信息）。
  - `409 Conflict`：用于状态冲突（如尝试取消已完成的任务）。
  - `416 Range Not Satisfiable`：专门用于文件下载时的范围请求错误。
  - `503 Service Unavailable`：用于环境重置预览等依赖外部系统就绪状态的检查失败。
- **异常链保留**：在抛出 `HTTPException` 时，普遍使用 `from exc` 语法保留原始异常堆栈，便于后端调试。
- **Worker 健壮性**：Worker 进程在执行 `build_deployment_package` 时使用 `asyncio.to_thread` 并在外层捕获所有异常，确保单个任务的失败不会中断轮询循环。
- **防御性编程**：在 `_audit` 等辅助函数中，使用裸 `except Exception` 防止副作用操作干扰主流程。