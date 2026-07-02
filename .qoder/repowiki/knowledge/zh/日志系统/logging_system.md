## 1. 使用的系统与工具
- **框架**：Python 标准库 `logging`。
- **配置方式**：在 Worker 进程入口（`worker.py`）通过 `logging.basicConfig` 进行全局初始化；API 服务（FastAPI）依赖 Uvicorn/Gunicorn 的默认日志输出，未在后端代码中显式配置根 Logger。
- **结构化程度**：非结构化文本日志。使用传统的 `%(asctime)s %(levelname)s %(name)s %(message)s` 格式，未集成 JSON 格式化器（如 `python-json-logger`）或高级日志库（如 `loguru`、`structlog`）。

## 2. 核心文件与模块
- **`backend/deployment_package_factory/worker.py`**：定义了后台构建任务的日志配置。设置了 `INFO` 级别，并指定了包含时间戳、级别、Logger 名称和消息的格式。
- **`backend/deployment_package_factory/api/deployment_packages.py`**：定义了 API 层的 Logger (`deployment_package_factory.api.deployment_packages`)，主要用于记录 Kubernetes 业务平台发现失败或审计事件记录异常等警告信息。
- **`backend/deployment_package_factory/services/deployment_packages/builder.py`**：定义了构建服务层的 Logger (`deployment_package_factory.services.deployment_packages.builder`)，用于记录容器镜像导出失败或辅助 Pod 清理失败等技术细节。

## 3. 架构与约定
- **命名空间规范**：遵循 Python 模块层级命名。例如 `deployment_package_factory.worker`、`deployment_package_factory.api.deployment_packages`。这种命名方式便于在日志输出中快速定位问题发生的模块。
- **日志级别策略**：
  - `INFO`：用于记录关键业务流程节点，如 Worker 启动、任务开始执行。
  - `WARNING`：用于记录非致命但需要关注的异常，如审计数据库写入失败、K8s 命名空间探测失败、本地 containerd 导出尝试失败等。
  - `ERROR`：目前代码中主要通过抛出 `PackageBuildError` 等异常由上层捕获处理，直接在 Logger 层面调用 `error` 的情况较少，更多依赖异常堆栈追踪。
- **异步环境适配**：Worker 采用 `asyncio` 运行，日志调用均为同步阻塞式（标准 `logging` 行为），在高频日志场景下可能对性能产生微小影响，但在当前构建任务场景下可接受。

## 4. 开发者应遵循的规则
- **获取 Logger**：必须使用 `logging.getLogger(__name__)` 获取模块级 Logger，严禁直接使用 `print` 进行生产环境调试。
- **参数化消息**：记录日志时应使用占位符风格（如 `LOGGER.info("Task %s started", task_id)`），避免使用 f-string 拼接，以减少不必要的字符串格式化开销。
- **异常记录**：在 `except` 块中记录日志时，若需要保留堆栈信息，应使用 `LOGGER.exception(...)` 或在 `basicConfig` 支持的情况下确保堆栈被正确输出。目前代码中多处使用 `LOGGER.warning("...: %s", exc)`，这只会记录异常消息而不会记录堆栈，建议在排查复杂错误时改进为 `exception` 级别。
- **敏感信息脱敏**：由于日志会输出到控制台并被收集系统抓取，严禁在日志中明文打印密码、Token 或密钥（如 `DEPLOYMENT_PACKAGE_SOURCE_REGISTRY_PASSWORD`）。