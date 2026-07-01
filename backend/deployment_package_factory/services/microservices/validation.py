from __future__ import annotations

import tarfile
from pathlib import Path

from deployment_package_factory.services.microservices.middleware_plugins import required_env_names


def validate_scaffold_artifact(project_root: Path, artifact_path: Path, rendered_files: list, tech_stack: str, middleware: list[str], required_files: list[str], micro_frontend_framework: str = "") -> dict[str, object]:
    checks: list[dict[str, object]] = []
    checks.append(_required_files(project_root, required_files))
    if tech_stack == "python-fastapi":
        checks.append(_python_syntax(project_root, rendered_files))
    checks.extend([_pipeline_files(project_root), _tech_stack_contract(project_root, tech_stack)])
    if micro_frontend_framework:
        checks.append(_micro_frontend_contract(project_root, micro_frontend_framework))
    checks.extend([_middleware_placeholders(project_root, middleware), _artifact_archive(artifact_path)])
    return {"passed": all(bool(item["passed"]) for item in checks), "checks": checks, "fileCount": len(rendered_files)}


def _required_files(project_root: Path, required_files: list[str]) -> dict[str, object]:
    missing = [item for item in required_files if not (project_root / item).exists()]
    return {"name": "required-files", "passed": not missing, "message": "关键文件已生成" if not missing else f"缺失文件: {', '.join(missing)}"}


def _python_syntax(project_root: Path, rendered_files: list) -> dict[str, object]:
    syntax_errors: list[str] = []
    for rendered_file in rendered_files:
        if rendered_file.path.suffix != ".py":
            continue
        file_path = project_root / Path(*rendered_file.path.parts)
        try:
            compile(file_path.read_text(encoding="utf-8"), str(rendered_file.path), "exec")
        except SyntaxError as exc:
            syntax_errors.append(f"{rendered_file.path}:{exc.lineno}")
    return {"name": "python-syntax", "passed": not syntax_errors, "message": "Python 源码语法检查通过" if not syntax_errors else f"语法错误: {', '.join(syntax_errors)}"}


def _pipeline_files(project_root: Path) -> dict[str, object]:
    snippets = {
        "Dockerfile": [["FROM"]],
        "Jenkinsfile": [["stage('Build')", 'stage("Build")', "stage('Build Image')", 'stage("Build Image")'], ["stage('Deploy')", 'stage("Deploy")']],
        "deploy.sh": [["helm upgrade --install"]],
        "deploy/k8s/deployment.yaml": [["kind: Deployment"]],
    }
    missing: list[str] = []
    for relative, expected in snippets.items():
        path = project_root / relative
        if not path.exists():
            missing.append(relative)
            continue
        content = path.read_text(encoding="utf-8")
        missing.extend(f"{relative}:{choices[0]}" for choices in expected if not any(snippet in content for snippet in choices))
    return {"name": "pipeline-files", "passed": not missing, "message": "构建和部署文件检查通过" if not missing else f"缺失内容: {', '.join(missing)}"}


def _middleware_placeholders(project_root: Path, middleware: list[str]) -> dict[str, object]:
    if not middleware:
        return {"name": "middleware-placeholders", "passed": True, "message": "未选择中间件"}
    env_file = project_root / ".env.template"
    config_file = project_root / "config" / "middleware.example.yaml"
    content = (env_file.read_text(encoding="utf-8") if env_file.exists() else "") + "\n" + (config_file.read_text(encoding="utf-8") if config_file.exists() else "")
    missing = [name for name in required_env_names(middleware) if name not in content]
    return {"name": "middleware-placeholders", "passed": not missing, "message": "中间件占位配置检查通过" if not missing else f"缺失占位符: {', '.join(missing)}"}


def _tech_stack_contract(project_root: Path, tech_stack: str) -> dict[str, object]:
    contracts = {
        "nodejs-express": {
            "package.json": ['"build":"tsc"', '"test":"node --test dist/tests/*.test.js"'],
            "src/interfaces/http/routes.ts": ["Router()", "/runtime"],
            "src/config/settings.ts": ["businessPlatformKey"],
            "src/infrastructure/middlewareClients.ts": ["middlewareHealth"],
        },
        "java-spring-cloud-alibaba": {
            "pom.xml": ["spring-cloud-starter-alibaba-nacos-discovery", "spring-boot-starter-data-jpa"],
            "src/main/resources/application.yml": ["nacos"],
            "src/main/java/com/example/Application.java": ["@SpringBootApplication"],
        },
        "vue3-vite": {"package.json": ["element-plus", "pinia"], "src/router/index.ts": ["createRouter"]},
        "react-vite": {"package.json": ["antd", "react"], "src/main.tsx": ["createRoot"]},
    }
    expected = contracts.get(tech_stack)
    if not expected:
        return {"name": "tech-stack-contract", "passed": True, "message": "默认技术栈检查通过"}
    missing: list[str] = []
    for relative, snippets in expected.items():
        path = project_root / relative
        if not path.exists():
            missing.append(relative)
            continue
        content = path.read_text(encoding="utf-8")
        missing.extend(f"{relative}:{snippet}" for snippet in snippets if snippet not in content)
    return {"name": "tech-stack-contract", "passed": not missing, "message": "技术栈契约检查通过" if not missing else f"缺失内容: {', '.join(missing)}"}


def _micro_frontend_contract(project_root: Path, framework: str) -> dict[str, object]:
    if not framework:
        return {"name": "micro-frontend-contract", "passed": True, "message": "未启用微前端"}
    packages = {"qiankun": "qiankun", "wujie": "wujie-vue3"}
    expected = packages.get(framework, framework)
    package_json = project_root / "package.json"
    content = package_json.read_text(encoding="utf-8") if package_json.exists() else ""
    passed = expected in content
    return {"name": "micro-frontend-contract", "passed": passed, "message": "微前端依赖检查通过" if passed else f"缺失依赖: {expected}"}


def _artifact_archive(artifact_path: Path) -> dict[str, object]:
    try:
        with tarfile.open(artifact_path, "r:gz") as tar:
            tar.getmembers()
        return {"name": "artifact-archive", "passed": True, "message": "项目压缩包可读取"}
    except (tarfile.TarError, OSError) as exc:
        return {"name": "artifact-archive", "passed": False, "message": f"项目压缩包不可读取: {exc}"}
