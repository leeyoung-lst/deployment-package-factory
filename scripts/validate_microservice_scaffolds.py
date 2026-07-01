from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from deployment_package_factory.services.microservices.scaffold import (  # noqa: E402
    MicroserviceScaffoldRequest,
    create_microservice_scaffold,
    find_scaffold_project_root,
)


@dataclass(frozen=True)
class Case:
    name: str
    service_key: str
    project_kind: str
    tech_stack: str
    middleware: list[str] = field(default_factory=list)
    micro_frontend_framework: str = ""


@dataclass
class CaseResult:
    case: str
    passed: bool
    project_root: str
    artifact_path: str
    checks: list[str]
    failures: list[str]


CASES = [
    Case("python-fastapi", "asset-python", "backend", "python-fastapi", ["redis", "postgresql"]),
    Case("nodejs-express", "asset-node", "backend", "nodejs-express", ["redis", "mongodb", "kafka", "mq"]),
    Case("java-spring-cloud-alibaba", "asset-java", "backend", "java-spring-cloud-alibaba", ["dm", "iotdb"]),
    Case("vue3-vite", "asset-vue", "frontend", "vue3-vite"),
    Case("vue3-vite-qiankun", "asset-vue-qiankun", "frontend", "vue3-vite", micro_frontend_framework="qiankun"),
    Case("vue3-vite-wujie", "asset-vue-wujie", "frontend", "vue3-vite", micro_frontend_framework="wujie"),
    Case("react-vite", "asset-react", "frontend", "react-vite"),
    Case("react-vite-qiankun", "asset-react-qiankun", "frontend", "react-vite", micro_frontend_framework="qiankun"),
    Case("react-vite-wujie", "asset-react-wujie", "frontend", "react-vite", micro_frontend_framework="wujie"),
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate generated microservice scaffold projects.")
    parser.add_argument("--output-dir", type=Path, help="Directory for generated validation artifacts. Defaults to a temporary directory.")
    parser.add_argument("--keep-output", action="store_true", help="Keep the temporary output directory after validation.")
    parser.add_argument("--run-build", action="store_true", help="Run local project build checks when npm/maven/python tooling is available.")
    parser.add_argument("--case", action="append", choices=[case.name for case in CASES], help="Limit validation to one or more named cases.")
    parser.add_argument("--json", action="store_true", help="Print a JSON summary after validation.")
    args = parser.parse_args()

    selected = [case for case in CASES if not args.case or case.name in set(args.case)]
    if args.output_dir:
        args.output_dir.mkdir(parents=True, exist_ok=True)
        return _run(args.output_dir, selected, args.run_build, args.json)

    with tempfile.TemporaryDirectory(prefix="microservice-scaffold-e2e-") as temp_dir:
        output_dir = Path(temp_dir)
        code = _run(output_dir, selected, args.run_build, args.json)
        if args.keep_output:
            kept = REPO_ROOT / "data" / "microservice-scaffold-e2e"
            if kept.exists():
                _remove_tree(kept)
            shutil.copytree(output_dir, kept)
            print(f"Kept output directory: {kept}")
        return code


def _run(output_dir: Path, cases: list[Case], run_build: bool, print_json: bool) -> int:
    print(f"Output directory: {output_dir}")
    results = [_validate_case(case, output_dir, run_build) for case in cases]
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        print(f"[{status}] {result.case}")
        for check in result.checks:
            print(f"  - {check}")
        for failure in result.failures:
            print(f"  ! {failure}")

    if print_json:
        print(json.dumps([result.__dict__ for result in results], ensure_ascii=False, indent=2))
    return 0 if all(result.passed for result in results) else 1


def _validate_case(case: Case, output_dir: Path, run_build: bool) -> CaseResult:
    checks: list[str] = []
    failures: list[str] = []
    request = _request(case)
    result = create_microservice_scaffold(request, output_dir=output_dir)
    project_root = find_scaffold_project_root(result.project_id, output_dir=output_dir)
    artifact_path = Path(result.artifact_path)

    _expect(result.validation.get("passed") is True, "scaffold validation passed", checks, failures)
    _expect(project_root is not None and project_root.exists(), "project root exists", checks, failures)
    _expect(artifact_path.exists(), "artifact tar.gz exists", checks, failures)

    if project_root:
        _validate_common_files(project_root, case, checks, failures)
        _validate_stack_files(project_root, case, checks, failures)
        _validate_namespace(project_root, checks, failures)
        if run_build:
            _run_build_checks(project_root, case, checks, failures)
    _validate_archive(artifact_path, case, checks, failures)

    return CaseResult(
        case=case.name,
        passed=not failures,
        project_root=str(project_root or ""),
        artifact_path=str(artifact_path),
        checks=checks,
        failures=failures,
    )


def _request(case: Case) -> MicroserviceScaffoldRequest:
    return MicroserviceScaffoldRequest(
        serviceKey=case.service_key,
        serviceName=case.name,
        projectKind=case.project_kind,
        techStack=case.tech_stack,
        microFrontendFramework=case.micro_frontend_framework,
        sourceEnv="test",
        businessPlatformKey="eam",
        businessPlatformProfile="4x60",
        businessPlatformName="EAM",
        businessPlatformNamespace="test-biz-eam-4x60",
        k8sNamespace="test-biz-eam-4x60",
        middleware=case.middleware,
        imageRegistry="registry.local",
        imageNamespace="business",
        gitGroup="business-services",
    )


def _validate_common_files(project_root: Path, case: Case, checks: list[str], failures: list[str]) -> None:
    required = ["README.md", ".env.template", "Dockerfile", "Jenkinsfile", "build.sh", "deploy.sh", "deploy/k8s/deployment.yaml"]
    for relative in required:
        _expect((project_root / relative).exists(), f"{relative} exists", checks, failures)
    readme = _read(project_root / "README.md")
    _expect(case.service_key in readme or case.name in readme, "README identifies service", checks, failures)


def _validate_stack_files(project_root: Path, case: Case, checks: list[str], failures: list[str]) -> None:
    if case.tech_stack == "python-fastapi":
        _expect((project_root / "src/app/main.py").exists(), "FastAPI main.py exists", checks, failures)
        _expect((project_root / "tests/test_api.py").exists(), "FastAPI tests exist", checks, failures)
        _compile_python(project_root, checks, failures)
        return
    if case.tech_stack == "nodejs-express":
        _expect((project_root / "src/interfaces/http/server.ts").exists(), "Node HTTP server exists", checks, failures)
        _expect('"build":"tsc"' in _read(project_root / "package.json"), "Node build script exists", checks, failures)
        return
    if case.tech_stack == "java-spring-cloud-alibaba":
        _expect((project_root / "pom.xml").exists(), "Java pom.xml exists", checks, failures)
        _expect((project_root / "src/main/resources/application.yml").exists(), "Java application.yml exists", checks, failures)
        return
    if case.tech_stack == "vue3-vite":
        _validate_vue(project_root, case, checks, failures)
        return
    if case.tech_stack == "react-vite":
        _validate_react(project_root, case, checks, failures)


def _validate_vue(project_root: Path, case: Case, checks: list[str], failures: list[str]) -> None:
    package_json = _read(project_root / "package.json")
    _expect((project_root / "vite.config.ts").exists(), "Vue vite.config.ts exists", checks, failures)
    _expect((project_root / "tsconfig.json").exists(), "Vue tsconfig.json exists", checks, failures)
    _expect((project_root / "src/main.ts").exists(), "Vue main.ts exists", checks, failures)
    _expect((project_root / "src/router/index.ts").exists(), "Vue router exists", checks, failures)
    _expect("element-plus" in package_json and "pinia" in package_json, "Vue dependencies exist", checks, failures)
    if case.micro_frontend_framework == "qiankun":
        _expect("qiankun" in package_json, "Vue qiankun dependency exists", checks, failures)
    if case.micro_frontend_framework == "wujie":
        _expect("wujie-vue3" in package_json, "Vue wujie dependency exists", checks, failures)


def _validate_react(project_root: Path, case: Case, checks: list[str], failures: list[str]) -> None:
    package_json = _read(project_root / "package.json")
    _expect((project_root / "vite.config.ts").exists(), "React vite.config.ts exists", checks, failures)
    _expect((project_root / "tsconfig.json").exists(), "React tsconfig.json exists", checks, failures)
    _expect((project_root / "src/main.tsx").exists(), "React main.tsx exists", checks, failures)
    _expect(not (project_root / "src/router/index.ts").exists(), "React does not include Vue router", checks, failures)
    _expect("antd" in package_json and "react-dom" in package_json, "React dependencies exist", checks, failures)
    if case.micro_frontend_framework == "qiankun":
        _expect("qiankun" in package_json, "React qiankun dependency exists", checks, failures)
    if case.micro_frontend_framework == "wujie":
        _expect("wujie-react" in package_json and "wujie-vue3" not in package_json, "React wujie adapter is correct", checks, failures)


def _validate_namespace(project_root: Path, checks: list[str], failures: list[str]) -> None:
    deployment = _read(project_root / "deploy/k8s/deployment.yaml")
    env_template = _read(project_root / ".env.template")
    _expect("namespace: test-biz-eam-4x60" in deployment, "K8s namespace uses business platform namespace", checks, failures)
    _expect("BUSINESS_PLATFORM_NAMESPACE=test-biz-eam-4x60" in env_template, "env template uses business platform namespace", checks, failures)


def _validate_archive(artifact_path: Path, case: Case, checks: list[str], failures: list[str]) -> None:
    try:
        with tarfile.open(artifact_path, "r:gz") as archive:
            names = set(archive.getnames())
        _expect(f"{case.service_key}/README.md" in names, "artifact contains README", checks, failures)
    except (OSError, tarfile.TarError) as exc:
        failures.append(f"artifact is not readable: {exc}")


def _compile_python(project_root: Path, checks: list[str], failures: list[str]) -> None:
    command = [sys.executable, "-m", "compileall", "-q", "src", "tests"]
    _run_command(command, project_root, "Python sources compile", checks, failures)


def _run_build_checks(project_root: Path, case: Case, checks: list[str], failures: list[str]) -> None:
    if case.tech_stack == "python-fastapi":
        _compile_python(project_root, checks, failures)
        return
    if case.tech_stack in {"nodejs-express", "vue3-vite", "react-vite"}:
        npm = shutil.which("npm")
        if not npm:
            failures.append("npm is required for --run-build")
            return
        _run_command([npm, "install"], project_root, "npm install", checks, failures)
        _run_command([npm, "run", "build"], project_root, "npm run build", checks, failures)
        return
    if case.tech_stack == "java-spring-cloud-alibaba":
        mvn = shutil.which("mvn")
        if not mvn:
            failures.append("mvn is required for --run-build")
            return
        _run_command([mvn, "-q", "-DskipTests", "package"], project_root, "maven package", checks, failures)


def _run_command(command: list[str], cwd: Path, label: str, checks: list[str], failures: list[str]) -> None:
    completed = subprocess.run(command, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if completed.returncode == 0:
        checks.append(label)
    else:
        output = "\n".join([completed.stdout or "", completed.stderr or ""])
        details = [line for line in output.strip().splitlines() if line.strip()]
        summary = " | ".join(details[-5:]) if details else str(completed.returncode)
        failures.append(f"{label} failed: {summary}")


def _remove_tree(path: Path) -> None:
    def clear_readonly(function, item, _excinfo):
        os.chmod(item, 0o700)
        function(item)

    shutil.rmtree(path, onexc=clear_readonly)


def _expect(condition: bool, message: str, checks: list[str], failures: list[str]) -> None:
    if condition:
        checks.append(message)
    else:
        failures.append(message)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


if __name__ == "__main__":
    raise SystemExit(main())
