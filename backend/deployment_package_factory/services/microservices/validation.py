from __future__ import annotations

import tarfile
from pathlib import Path

import yaml

from deployment_package_factory.services.microservices.feature_specs import FeatureSpec, enabled_feature_specs_from_flags
from deployment_package_factory.services.microservices.middleware_plugins import required_env_names


def validate_scaffold_artifact(project_root: Path, artifact_path: Path, rendered_files: list, tech_stack: str, middleware: list[str], required_files: list[str], micro_frontend_framework: str = "", mcp_server_enabled: bool = False) -> dict[str, object]:
    checks: list[dict[str, object]] = []
    checks.append(_required_files(project_root, required_files))
    if tech_stack == "python-fastapi":
        checks.append(_python_syntax(project_root, rendered_files))
    checks.extend([_pipeline_files(project_root), _helm_templates(project_root), _tech_stack_contract(project_root, tech_stack)])
    if micro_frontend_framework:
        checks.append(_micro_frontend_contract(project_root, micro_frontend_framework))
    checks.extend(_feature_contract(project_root, tech_stack, feature) for feature in enabled_feature_specs_from_flags(mcp_server_enabled=mcp_server_enabled))
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
    deployment = _read_yaml(project_root / "deploy/k8s/deployment.yaml")
    if deployment and not _deployment_has_env_sources(deployment):
        missing.append("deploy/k8s/deployment.yaml:envFrom")
    return {"name": "pipeline-files", "passed": not missing, "message": "构建和部署文件检查通过" if not missing else f"缺失内容: {', '.join(missing)}"}


def _helm_templates(project_root: Path) -> dict[str, object]:
    charts = [path for path in (project_root / "deploy" / "helm").glob("*") if path.is_dir()]
    if not charts:
        return {"name": "helm-templates", "passed": False, "message": "缺失 Helm chart 目录"}
    chart = charts[0]
    files = {
        "values": chart / "values.yaml",
        "deployment": chart / "templates" / "deployment.yaml",
        "configmap": chart / "templates" / "configmap.yaml",
        "secret": chart / "templates" / "secret.yaml",
    }
    missing = [name for name, path in files.items() if not path.exists()]
    if missing:
        return {"name": "helm-templates", "passed": False, "message": f"缺失 Helm 文件: {', '.join(missing)}"}
    deployment = files["deployment"].read_text(encoding="utf-8")
    configmap = files["configmap"].read_text(encoding="utf-8")
    secret = files["secret"].read_text(encoding="utf-8")
    values = _read_yaml(files["values"])
    helpers = chart / "templates" / "_helpers.tpl"
    issues: list[str] = []
    if "envFrom:" not in deployment or "configMapRef:" not in deployment or "secretRef:" not in deployment:
        issues.append("deployment 未挂载 ConfigMap/Secret")
    if "ConfigMap" not in configmap or "Secret" not in secret:
        issues.append("configmap/secret 模板类型错误")
    if 'include "' in "\n".join([deployment, configmap, secret]) and not helpers.exists():
        issues.append("使用 include 但缺失 _helpers.tpl")
    if not isinstance(values, dict) or not values.get("image") or not values.get("service"):
        issues.append("values.yaml 缺失 image/service 配置")
    return {"name": "helm-templates", "passed": not issues, "message": "Helm 模板检查通过" if not issues else f"Helm 模板问题: {', '.join(issues)}"}


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
        "vue3-vite": {"package.json": ["element-plus", "pinia"], "src/router/index.ts": ["createRouter"], "vite.config.ts": ["@vitejs/plugin-vue"]},
        "react-vite": {"package.json": ["antd", "react"], "src/main.tsx": ["createRoot"], "vite.config.ts": ["@vitejs/plugin-react"]},
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
    package_json = project_root / "package.json"
    content = package_json.read_text(encoding="utf-8") if package_json.exists() else ""
    is_react = "@vitejs/plugin-react" in content
    packages = {"qiankun": "qiankun", "wujie": "wujie-react" if is_react else "wujie-vue3"}
    expected = packages.get(framework, framework)
    passed = expected in content
    return {"name": "micro-frontend-contract", "passed": passed, "message": "微前端依赖检查通过" if passed else f"缺失依赖: {expected}"}


def _feature_contract(project_root: Path, tech_stack: str, feature: FeatureSpec) -> dict[str, object]:
    files = feature.required_files(tech_stack)
    missing = [relative for relative in files if not (project_root / relative).exists()]
    content = "\n".join((project_root / relative).read_text(encoding="utf-8") for relative in files if (project_root / relative).exists())
    missing.extend(f"content:{snippet}" for snippet in feature.contract_snippets if snippet not in content)
    return {
        "name": f"{feature.key}-contract",
        "passed": not missing,
        "message": f"{feature.name} 示例检查通过" if not missing else f"缺失 {feature.name} 内容: {', '.join(missing)}",
    }


def _artifact_archive(artifact_path: Path) -> dict[str, object]:
    try:
        with tarfile.open(artifact_path, "r:gz") as tar:
            tar.getmembers()
        return {"name": "artifact-archive", "passed": True, "message": "项目压缩包可读取"}
    except (tarfile.TarError, OSError) as exc:
        return {"name": "artifact-archive", "passed": False, "message": f"项目压缩包不可读取: {exc}"}


def _read_yaml(path: Path) -> object:
    if not path.exists():
        return None
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError:
        return None


def _deployment_has_env_sources(deployment: object) -> bool:
    if not isinstance(deployment, dict):
        return False
    containers = (
        deployment.get("spec", {})
        .get("template", {})
        .get("spec", {})
        .get("containers", [])
    )
    if not isinstance(containers, list) or not containers:
        return False
    env_from = containers[0].get("envFrom", []) if isinstance(containers[0], dict) else []
    if not isinstance(env_from, list):
        return False
    has_configmap = any(isinstance(item, dict) and "configMapRef" in item for item in env_from)
    has_secret = any(isinstance(item, dict) and "secretRef" in item for item in env_from)
    return has_configmap and has_secret
