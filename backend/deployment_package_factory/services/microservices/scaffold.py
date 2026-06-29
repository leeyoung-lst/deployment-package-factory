from __future__ import annotations

import hashlib
import re
import shutil
import subprocess
import tarfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

from deployment_package_factory.services.microservices.middleware_plugins import env_default_lines, middleware_yaml
from deployment_package_factory.services.microservices.templates import (
    MIDDLEWARE,
    PROJECT_KINDS,
    TECH_STACKS,
    TECH_STACK_PROJECT_KIND,
    generic_required_files,
    render_generic_template,
)
from deployment_package_factory.services.microservices.validation import validate_scaffold_artifact


DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[4] / "data" / "microservice-projects"
SUPPORTED_TECH_STACKS = {
    key: name for key, name in TECH_STACKS.items()
}
SUPPORTED_MIDDLEWARE = {
    key: name for key, name in MIDDLEWARE.items()
}
K8S_NAME_RE = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?")
IMAGE_SEGMENT_RE = re.compile(r"[a-z0-9]+(?:[._-][a-z0-9]+)*")


class MicroserviceScaffoldRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    service_key: str = Field(alias="serviceKey")
    service_name: str = Field(alias="serviceName")
    description: str = ""
    project_kind: str = Field(default="backend", alias="projectKind")
    tech_stack: str = Field(default="python-fastapi", alias="techStack")
    package_name: str = Field(default="", alias="packageName")
    port: int = 8000
    middleware: list[str] = Field(default_factory=list)
    source_env: str = Field(alias="sourceEnv")
    business_platform_key: str = Field(alias="businessPlatformKey")
    business_platform_profile: str = Field(default="", alias="businessPlatformProfile")
    business_platform_name: str = Field(default="", alias="businessPlatformName")
    business_platform_namespace: str = Field(default="", alias="businessPlatformNamespace")
    git_group: str = Field(default="", alias="gitGroup")
    image_registry: str = Field(default="", alias="imageRegistry")
    image_namespace: str = Field(default="", alias="imageNamespace")
    k8s_namespace: str = Field(default="", alias="k8sNamespace")

    @field_validator("service_key")
    @classmethod
    def validate_service_key(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not K8S_NAME_RE.fullmatch(normalized):
            raise ValueError("serviceKey must be a valid Kubernetes name: lowercase letters, numbers, and hyphens, starting and ending with a letter or number")
        return normalized

    @field_validator("git_group")
    @classmethod
    def validate_git_group(cls, value: str) -> str:
        normalized = value.strip().strip("/").lower()
        if not normalized:
            return normalized
        segments = normalized.split("/")
        if any(not IMAGE_SEGMENT_RE.fullmatch(segment) for segment in segments):
            raise ValueError("gitGroup must contain lowercase path segments separated by slash")
        return normalized

    @field_validator("image_registry")
    @classmethod
    def validate_image_registry(cls, value: str) -> str:
        normalized = value.strip().rstrip("/")
        if not normalized:
            return normalized
        if "/" in normalized or any(char.isspace() for char in normalized):
            raise ValueError("imageRegistry must be a registry host, optionally with port")
        return normalized

    @field_validator("image_namespace")
    @classmethod
    def validate_image_namespace(cls, value: str) -> str:
        normalized = value.strip().strip("/").lower()
        if not normalized:
            return normalized
        if any(not IMAGE_SEGMENT_RE.fullmatch(segment) for segment in normalized.split("/")):
            raise ValueError("imageNamespace must contain lowercase image path segments")
        return normalized

    @field_validator("k8s_namespace")
    @classmethod
    def validate_k8s_namespace(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized and not K8S_NAME_RE.fullmatch(normalized):
            raise ValueError("k8sNamespace must be a valid Kubernetes namespace")
        return normalized

    @field_validator("tech_stack")
    @classmethod
    def validate_tech_stack(cls, value: str) -> str:
        if value not in SUPPORTED_TECH_STACKS:
            raise ValueError(f"Unsupported techStack: {value}")
        return value

    @field_validator("port")
    @classmethod
    def validate_port(cls, value: int) -> int:
        if value < 1 or value > 65535:
            raise ValueError("port must be between 1 and 65535")
        return value

    @field_validator("project_kind")
    @classmethod
    def validate_project_kind(cls, value: str) -> str:
        if value not in PROJECT_KINDS:
            raise ValueError(f"Unsupported projectKind: {value}")
        return value

    def model_post_init(self, __context: object) -> None:
        expected = TECH_STACK_PROJECT_KIND.get(self.tech_stack)
        if expected and self.project_kind != expected:
            raise ValueError(f"projectKind must be {expected} for techStack {self.tech_stack}")

    @field_validator("middleware")
    @classmethod
    def validate_middleware(cls, value: list[str]) -> list[str]:
        unsupported = sorted(set(value) - set(SUPPORTED_MIDDLEWARE))
        if unsupported:
            raise ValueError(f"Unsupported middleware: {', '.join(unsupported)}")
        return sorted(set(value))


class MicroserviceScaffoldResult(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    project_id: str = Field(alias="projectId")
    service_key: str = Field(alias="serviceKey")
    service_name: str = Field(alias="serviceName")
    tech_stack: str = Field(alias="techStack")
    source_env: str = Field(alias="sourceEnv")
    business_platform_key: str = Field(alias="businessPlatformKey")
    business_platform_profile: str = Field(alias="businessPlatformProfile")
    business_platform_name: str = Field(alias="businessPlatformName")
    business_platform_namespace: str = Field(alias="businessPlatformNamespace")
    artifact_name: str = Field(alias="artifactName")
    artifact_path: str = Field(alias="artifactPath")
    artifact_size: int = Field(alias="artifactSize")
    sha256: str
    download_url: str = Field(alias="downloadUrl")
    download_command: str = Field(alias="downloadCommand")
    clone_command: str = Field(alias="cloneCommand")
    generated_files: list[str] = Field(alias="generatedFiles")
    validation: dict[str, object] = Field(default_factory=lambda: {"passed": False, "checks": [], "fileCount": 0})


class MicroserviceScaffoldOptions(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    project_kinds: list[dict[str, str]] = Field(alias="projectKinds")
    tech_stacks: list[dict[str, str]] = Field(alias="techStacks")
    middleware: list[dict[str, str]]


@dataclass(frozen=True)
class RenderedFile:
    path: PurePosixPath
    content: str
    executable: bool = False


def scaffold_options() -> MicroserviceScaffoldOptions:
    return MicroserviceScaffoldOptions(
        projectKinds=[{"key": key, "name": name} for key, name in PROJECT_KINDS.items()],
        techStacks=[{"key": key, "name": name, "projectKind": TECH_STACK_PROJECT_KIND[key]} for key, name in SUPPORTED_TECH_STACKS.items()],
        middleware=[{"key": key, "name": name} for key, name in SUPPORTED_MIDDLEWARE.items()],
    )


def create_microservice_scaffold(
    request: MicroserviceScaffoldRequest,
    *,
    output_dir: Path | None = None,
) -> MicroserviceScaffoldResult:
    root = output_dir or DEFAULT_OUTPUT_DIR
    work_dir = root / "work"
    artifact_dir = root / "artifacts"
    work_dir.mkdir(parents=True, exist_ok=True)
    artifact_dir.mkdir(parents=True, exist_ok=True)

    project_id = f"svc-{uuid4().hex[:12]}"
    project_root = work_dir / f"{request.service_key}-{project_id}"
    if project_root.exists():
        shutil.rmtree(project_root)
    project_root.mkdir(parents=True)

    rendered_files = _render_scaffold(request)
    for rendered_file in rendered_files:
        _write_file(project_root / Path(*rendered_file.path.parts), rendered_file.content, rendered_file.executable)
    _initialize_git(project_root)

    artifact_name = f"{request.service_key}-{project_id}.tar.gz"
    artifact_path = artifact_dir / artifact_name
    with tarfile.open(artifact_path, "w:gz") as tar:
        tar.add(project_root, arcname=request.service_key)
    digest = _file_sha256(artifact_path)
    validation = _validate_scaffold(project_root, artifact_path, rendered_files, request.tech_stack, request.middleware)

    return MicroserviceScaffoldResult(
        projectId=project_id,
        serviceKey=request.service_key,
        serviceName=request.service_name,
        techStack=request.tech_stack,
        sourceEnv=request.source_env,
        businessPlatformKey=request.business_platform_key,
        businessPlatformProfile=request.business_platform_profile,
        businessPlatformName=request.business_platform_name or request.business_platform_key,
        businessPlatformNamespace=request.business_platform_namespace or request.k8s_namespace or request.business_platform_key,
        artifactName=artifact_name,
        artifactPath=str(artifact_path),
        artifactSize=artifact_path.stat().st_size,
        sha256=digest,
        downloadUrl=f"/api/microservices/{project_id}/download",
        downloadCommand=f"curl -fL /api/microservices/{project_id}/download -o {artifact_name}",
        cloneCommand=f"curl -fL /api/microservices/{project_id}/download -o {artifact_name} && tar -xzf {artifact_name} && cd {request.service_key}",
        generatedFiles=sorted(str(file.path) for file in rendered_files),
        validation=validation,
    )


def _render_scaffold(request: MicroserviceScaffoldRequest) -> list[RenderedFile]:
    if request.tech_stack == "python-fastapi":
        return _render_python_fastapi(request)
    return [RenderedFile(item.path, item.content, item.executable) for item in render_generic_template(request)]


def find_scaffold_artifact(project_id: str, *, output_dir: Path | None = None) -> Path | None:
    if not re.fullmatch(r"svc-[a-f0-9]{12}", project_id):
        return None
    artifact_dir = (output_dir or DEFAULT_OUTPUT_DIR) / "artifacts"
    matches = list(artifact_dir.glob(f"*-{project_id}.tar.gz"))
    return matches[0] if matches else None


def _render_python_fastapi(request: MicroserviceScaffoldRequest) -> list[RenderedFile]:
    context = _context(request)
    files = [
        RenderedFile(PurePosixPath(".gitignore"), _gitignore()),
        RenderedFile(PurePosixPath(".env.template"), _env_template(context)),
        RenderedFile(PurePosixPath("README.md"), _readme(context)),
        RenderedFile(PurePosixPath("requirements.txt"), _requirements(context)),
        RenderedFile(PurePosixPath("Dockerfile"), _dockerfile(context)),
        RenderedFile(PurePosixPath("Jenkinsfile"), _jenkinsfile(context)),
        RenderedFile(PurePosixPath("build.sh"), _build_sh(context), executable=True),
        RenderedFile(PurePosixPath("build.ps1"), _build_ps1(context)),
        RenderedFile(PurePosixPath("deploy.sh"), _deploy_sh(context), executable=True),
        RenderedFile(PurePosixPath("deploy.ps1"), _deploy_ps1(context)),
        RenderedFile(PurePosixPath("migrate.sh"), _migrate_sh(context), executable=True),
        RenderedFile(PurePosixPath("migrate.ps1"), _migrate_ps1(context)),
        RenderedFile(PurePosixPath("run-local.sh"), _run_local_sh(context), executable=True),
        RenderedFile(PurePosixPath("run-local.ps1"), _run_local_ps1(context)),
        RenderedFile(PurePosixPath("test.sh"), _test_sh(), executable=True),
        RenderedFile(PurePosixPath("test.ps1"), _test_ps1()),
        RenderedFile(PurePosixPath("config/middleware.example.yaml"), middleware_yaml(request.middleware)),
        RenderedFile(PurePosixPath("src/app/__init__.py"), ""),
        RenderedFile(PurePosixPath("src/app/main.py"), _fastapi_main(context)),
        RenderedFile(PurePosixPath("src/app/config.py"), _fastapi_config(context)),
        RenderedFile(PurePosixPath("src/app/domain/__init__.py"), ""),
        RenderedFile(PurePosixPath("src/app/domain/models.py"), _domain_models()),
        RenderedFile(PurePosixPath("src/app/domain/services.py"), _domain_services()),
        RenderedFile(PurePosixPath("src/app/application/__init__.py"), ""),
        RenderedFile(PurePosixPath("src/app/application/health.py"), _health_service(context)),
        RenderedFile(PurePosixPath("src/app/application/use_cases.py"), _application_use_cases()),
        RenderedFile(PurePosixPath("src/app/infrastructure/__init__.py"), ""),
        RenderedFile(PurePosixPath("src/app/interfaces/__init__.py"), ""),
        RenderedFile(PurePosixPath("src/app/interfaces/http/__init__.py"), ""),
        RenderedFile(PurePosixPath("src/app/interfaces/http/routes.py"), _fastapi_routes(context)),
        RenderedFile(PurePosixPath("tests/__init__.py"), ""),
        RenderedFile(PurePosixPath("tests/test_api.py"), _api_tests(context)),
        RenderedFile(PurePosixPath("deploy/k8s/namespace.yaml"), _k8s_namespace(context)),
        RenderedFile(PurePosixPath("deploy/k8s/deployment.yaml"), _k8s_deployment(context)),
        RenderedFile(PurePosixPath("deploy/k8s/service.yaml"), _k8s_service(context)),
        RenderedFile(PurePosixPath("deploy/k8s/configmap.yaml"), _k8s_configmap(context)),
        RenderedFile(PurePosixPath("deploy/k8s/secret.template.yaml"), _k8s_secret(context)),
        RenderedFile(PurePosixPath("deploy/k8s/ingress.template.yaml"), _k8s_ingress(context)),
        RenderedFile(PurePosixPath(f"deploy/helm/{request.service_key}/Chart.yaml"), _helm_chart(context)),
        RenderedFile(PurePosixPath(f"deploy/helm/{request.service_key}/values.yaml"), _helm_values(context)),
        RenderedFile(PurePosixPath(f"deploy/helm/{request.service_key}/templates/_helpers.tpl"), _helm_helpers(context)),
        RenderedFile(PurePosixPath(f"deploy/helm/{request.service_key}/templates/deployment.yaml"), _helm_deployment(context)),
        RenderedFile(PurePosixPath(f"deploy/helm/{request.service_key}/templates/service.yaml"), _helm_service(context)),
        RenderedFile(PurePosixPath(f"deploy/helm/{request.service_key}/templates/configmap.yaml"), _helm_configmap(context)),
        RenderedFile(PurePosixPath(f"deploy/helm/{request.service_key}/templates/secret.yaml"), _helm_secret(context)),
        RenderedFile(PurePosixPath(f"deploy/helm/{request.service_key}/templates/ingress.yaml"), _helm_ingress(context)),
    ]
    if "redis" in request.middleware:
        files.append(RenderedFile(PurePosixPath("src/app/infrastructure/redis_client.py"), _redis_client()))
    if "postgresql" in request.middleware:
        files.extend(
            [
                RenderedFile(PurePosixPath("src/app/infrastructure/postgres_repository.py"), _postgres_repository()),
                RenderedFile(PurePosixPath("db/init/001_items.sql"), _postgres_init_sql()),
            ]
        )
    return files


def _context(request: MicroserviceScaffoldRequest) -> dict[str, object]:
    image = f"{request.image_registry.rstrip('/')}/{request.image_namespace.strip('/')}/{request.service_key}"
    return {
        "service_key": request.service_key,
        "service_name": request.service_name,
        "description": request.description or request.service_name,
        "port": request.port,
        "middleware": request.middleware,
        "image": image,
        "source_env": request.source_env,
        "business_platform_key": request.business_platform_key,
        "business_platform_profile": request.business_platform_profile,
        "business_platform_name": request.business_platform_name or request.business_platform_key,
        "business_platform_namespace": request.business_platform_namespace or request.k8s_namespace or request.business_platform_key,
        "k8s_namespace": request.k8s_namespace or request.business_platform_namespace or request.business_platform_key,
        "git_group": request.git_group,
    }


def _write_file(path: Path, content: str, executable: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")
    if executable:
        path.chmod(path.stat().st_mode | 0o111)


def _validate_scaffold(project_root: Path, artifact_path: Path, rendered_files: list[RenderedFile], tech_stack: str = "python-fastapi", middleware: list[str] | None = None) -> dict[str, object]:
    required_files = generic_required_files(tech_stack) if tech_stack != "python-fastapi" else [
        "README.md",
        ".env.template",
        "Dockerfile",
        "Jenkinsfile",
        "build.sh",
        "deploy.sh",
        "migrate.sh",
        "run-local.sh",
        "test.sh",
        "src/app/main.py",
        "src/app/config.py",
        "src/app/domain/models.py",
        "src/app/application/use_cases.py",
        "src/app/interfaces/http/routes.py",
        "tests/test_api.py",
        "deploy/k8s/namespace.yaml",
        "deploy/k8s/deployment.yaml",
        "deploy/k8s/service.yaml",
        "deploy/k8s/configmap.yaml",
        "deploy/k8s/secret.template.yaml",
        "deploy/k8s/ingress.template.yaml",
        "deploy/helm",
    ]
    return validate_scaffold_artifact(project_root, artifact_path, rendered_files, tech_stack, middleware or [], required_files)


def _initialize_git(project_root: Path) -> None:
    if not shutil.which("git"):
        return
    try:
        subprocess.run(["git", "init", "-b", "main"], cwd=project_root, check=True, capture_output=True, text=True)
        subprocess.run(["git", "add", "."], cwd=project_root, check=True, capture_output=True, text=True)
        subprocess.run(
            ["git", "-c", "user.name=Deployment Package Factory", "-c", "user.email=factory@example.local", "commit", "-m", "Initial scaffold"],
            cwd=project_root,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError:
        return


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _gitignore() -> str:
    return "\n".join([".env", "__pycache__/", ".pytest_cache/", ".venv/", "dist/", "*.pyc", ""]) 


def _env_template(context: dict[str, object]) -> str:
    lines = [
        f"SERVICE_NAME={context['service_key']}",
        f"BUSINESS_PLATFORM_KEY={context['business_platform_key']}",
        f"BUSINESS_PLATFORM_NAMESPACE={context['business_platform_namespace']}",
        f"SOURCE_ENV={context['source_env']}",
        f"APP_PORT={context['port']}",
        "LOG_LEVEL=INFO",
    ]
    if "redis" in context["middleware"]:
        lines.extend(["REDIS_URL=redis://redis:6379/0"])
    if "postgresql" in context["middleware"]:
        lines.extend(["POSTGRES_DSN=postgresql://app:__REPLACE_WITH_POSTGRES_PASSWORD__@postgresql:5432/app"])
    lines.extend(item for item in env_default_lines(context["middleware"]) if not item.startswith(("REDIS_", "POSTGRESQL_")))
    return "\n".join(lines) + "\n"


def _readme(context: dict[str, object]) -> str:
    middleware = ", ".join(context["middleware"]) or "none"
    return f"""# {context['service_name']}

{context['description']}

## Structure

```text
src/app/
  domain/          # Domain model and domain service, no framework dependency
  application/     # Use cases and orchestration
  infrastructure/  # Redis/PostgreSQL adapters and external integrations
  interfaces/http/ # FastAPI routes
```

## Local development

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
cp .env.template .env
./run-local.sh
```

Windows PowerShell:

```powershell
python -m venv .venv
.\\.venv\\Scripts\\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.template .env
.\\run-local.ps1
```

## Smoke test

```bash
./test.sh
curl http://127.0.0.1:{context['port']}/health
curl -X POST http://127.0.0.1:{context['port']}/api/v1/items/demo-item
```

## Build image

```bash
./build.sh {context['image']}:dev
```

## Git

The generated archive contains an initialized Git repository when `git` is available on the factory host.
If your extracted directory has no `.git`, run:

```bash
git init -b main
git add .
git commit -m "Initial scaffold"
```

## Middleware

Enabled middleware: {middleware}

Middleware checks are non-blocking in local development. If Redis or PostgreSQL is not running, `/api/v1/runtime` returns a clear `ok: false` status instead of crashing the service.

## Business platform

- Platform: {context['business_platform_name']} ({context['business_platform_key']})
- Profile: {context['business_platform_profile'] or 'default'}
- Namespace: {context['business_platform_namespace']}
- Source environment: {context['source_env']}

## Deploy

```bash
./migrate.sh
./deploy.sh {context['image']}:dev
```

`deploy.sh` uses Helm by default:

```bash
helm upgrade --install {context['service_key']} deploy/helm/{context['service_key']} --namespace {context['k8s_namespace']} --create-namespace
```

Plain Kubernetes YAML files are also generated under `deploy/k8s/` for debugging or restricted environments.
"""


def _requirements(context: dict[str, object]) -> str:
    dependencies = [
        "fastapi>=0.115.0",
        "uvicorn[standard]>=0.30.0",
        "pydantic-settings>=2.5.0",
        "pytest>=8.0.0",
        "httpx>=0.27.0",
    ]
    if "redis" in context["middleware"]:
        dependencies.append("redis>=5.0.0")
    if "postgresql" in context["middleware"]:
        dependencies.append("psycopg[binary]>=3.2.0")
    return "\n".join(dependencies) + "\n"


def _dockerfile(context: dict[str, object]) -> str:
    return f"""FROM python:3.12-slim

WORKDIR /app
ENV PYTHONPATH=/app/src
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY src ./src
RUN groupadd -r app && useradd -r -g app -u 10001 app && chown -R app:app /app
USER 10001
EXPOSE {context['port']}
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "{context['port']}"]
"""


def _jenkinsfile(context: dict[str, object]) -> str:
    return f"""pipeline {{
  agent any
  environment {{
    IMAGE = "{context['image']}:${{env.BUILD_NUMBER}}"
    K8S_NAMESPACE = "{context['k8s_namespace']}"
    RELEASE_NAME = "{context['service_key']}"
    CHART = "deploy/helm/{context['service_key']}"
  }}
  stages {{
    stage('Install') {{
      steps {{
        sh 'python -m pip install -r requirements.txt'
      }}
    }}
    stage('Test') {{
      steps {{
        sh 'PYTHONPATH=src pytest -q'
      }}
    }}
    stage('Build Image') {{
      steps {{
        sh 'docker build -t $IMAGE .'
      }}
    }}
    stage('Push Image') {{
      steps {{
        sh 'docker push $IMAGE'
      }}
    }}
    stage('Deploy') {{
      steps {{
        sh './deploy.sh $IMAGE'
      }}
    }}
  }}
}}
"""


def _build_sh(context: dict[str, object]) -> str:
    return f"""#!/usr/bin/env bash
set -euo pipefail
IMAGE="${{1:-{context['image']}:dev}}"
docker build -t "${{IMAGE}}" .
"""


def _build_ps1(context: dict[str, object]) -> str:
    return f"""param(
  [string]$Image = "{context['image']}:dev"
)
$ErrorActionPreference = "Stop"
docker build -t $Image .
"""


def _deploy_sh(context: dict[str, object]) -> str:
    return f"""#!/usr/bin/env bash
set -euo pipefail
IMAGE="${{1:-{context['image']}:dev}}"
RELEASE="${{RELEASE_NAME:-{context['service_key']}}}"
NAMESPACE="${{K8S_NAMESPACE:-{context['k8s_namespace']}}}"
CHART="${{CHART:-deploy/helm/{context['service_key']}}}"
REPOSITORY="${{IMAGE%:*}}"
TAG="${{IMAGE##*:}}"
helm upgrade --install "${{RELEASE}}" "${{CHART}}" \\
  --namespace "${{NAMESPACE}}" \\
  --create-namespace \\
  --set image.repository="${{REPOSITORY}}" \\
  --set image.tag="${{TAG}}"
"""


def _deploy_ps1(context: dict[str, object]) -> str:
    return f"""param(
  [string]$Image = "{context['image']}:dev",
  [string]$Release = "{context['service_key']}",
  [string]$Namespace = "{context['k8s_namespace']}",
  [string]$Chart = "deploy/helm/{context['service_key']}"
)
$ErrorActionPreference = "Stop"
$lastColon = $Image.LastIndexOf(":")
if ($lastColon -lt 0) {{ throw "Image must include tag: $Image" }}
$repository = $Image.Substring(0, $lastColon)
$tag = $Image.Substring($lastColon + 1)
helm upgrade --install $Release $Chart --namespace $Namespace --create-namespace --set image.repository=$repository --set image.tag=$tag
"""


def _migrate_sh(context: dict[str, object]) -> str:
    if "postgresql" not in context["middleware"]:
        return """#!/usr/bin/env bash
set -euo pipefail
echo "No database migration is configured for this service."
"""
    return """#!/usr/bin/env bash
set -euo pipefail
NAMESPACE="${K8S_NAMESPACE:-""" + str(context["k8s_namespace"]) + """}"
POSTGRES_POD="${POSTGRES_POD:-postgresql-0}"
POSTGRES_DB="${POSTGRES_DB:-app}"
POSTGRES_USER="${POSTGRES_USER:-app}"
kubectl -n "${NAMESPACE}" exec -i "${POSTGRES_POD}" -- psql -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" < db/init/001_items.sql
"""


def _migrate_ps1(context: dict[str, object]) -> str:
    if "postgresql" not in context["middleware"]:
        return """$ErrorActionPreference = "Stop"
Write-Host "No database migration is configured for this service."
"""
    return f"""param(
  [string]$Namespace = "{context['k8s_namespace']}",
  [string]$PostgresPod = "postgresql-0",
  [string]$PostgresDb = "app",
  [string]$PostgresUser = "app"
)
$ErrorActionPreference = "Stop"
Get-Content db/init/001_items.sql | kubectl -n $Namespace exec -i $PostgresPod -- psql -U $PostgresUser -d $PostgresDb
"""


def _run_local_sh(context: dict[str, object]) -> str:
    return f"""#!/usr/bin/env bash
set -euo pipefail
export PYTHONPATH="${{PYTHONPATH:-src}}"
uvicorn app.main:app --reload --host 0.0.0.0 --port "${{APP_PORT:-{context['port']}}}"
"""


def _run_local_ps1(context: dict[str, object]) -> str:
    return f"""$ErrorActionPreference = "Stop"
$env:PYTHONPATH = if ($env:PYTHONPATH) {{ $env:PYTHONPATH }} else {{ "src" }}
$port = if ($env:APP_PORT) {{ $env:APP_PORT }} else {{ "{context['port']}" }}
uvicorn app.main:app --reload --host 0.0.0.0 --port $port
"""


def _test_sh() -> str:
    return """#!/usr/bin/env bash
set -euo pipefail
export PYTHONPATH="${PYTHONPATH:-src}"
pytest -q
"""


def _test_ps1() -> str:
    return """$ErrorActionPreference = "Stop"
$env:PYTHONPATH = if ($env:PYTHONPATH) { $env:PYTHONPATH } else { "src" }
pytest -q
"""


def _fastapi_main(context: dict[str, object]) -> str:
    return f"""from fastapi import FastAPI

from app.interfaces.http.routes import router
from app.config import settings

app = FastAPI(title="{context['service_name']}", version="0.1.0")
app.include_router(router)


@app.get("/health")
def health():
    return {{"status": "ok", "service": settings.service_name}}
"""


def _fastapi_config(context: dict[str, object]) -> str:
    fields = [
        "from pydantic_settings import BaseSettings, SettingsConfigDict",
        "",
        "",
        "class Settings(BaseSettings):",
        '    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")',
        f'    service_name: str = "{context["service_key"]}"',
        f'    business_platform_key: str = "{context["business_platform_key"]}"',
        f'    business_platform_namespace: str = "{context["business_platform_namespace"]}"',
        f'    source_env: str = "{context["source_env"]}"',
        f"    app_port: int = {context['port']}",
        '    log_level: str = "INFO"',
    ]
    if "redis" in context["middleware"]:
        fields.append('    redis_url: str = "redis://localhost:6379/0"')
    if "postgresql" in context["middleware"]:
        fields.append('    postgres_dsn: str = "postgresql://app:app@localhost:5432/app"')
    fields.extend(["", "", "settings = Settings()", ""])
    return "\n".join(fields)


def _fastapi_routes(context: dict[str, object]) -> str:
    imports = [
        "from fastapi import APIRouter",
        "",
        "from app.application.health import collect_health",
        "from app.application.use_cases import create_demo_item",
    ]
    body = [
        "",
        'router = APIRouter(prefix="/api/v1")',
        "",
        "",
        '@router.get("/hello")',
        "def hello():",
        f"    return {{\"message\": \"hello from {context['service_key']}\"}}",
        "",
        "",
        '@router.post("/items/{name}")',
        "def create_item(name: str):",
        "    return create_demo_item(name).model_dump()",
        "",
        "",
        '@router.get("/runtime")',
        "def runtime():",
        "    return collect_health()",
    ]
    return "\n".join(imports + body) + "\n"


def _domain_models() -> str:
    return """from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class DemoItem:
    name: str
    normalized_name: str
    created_at: datetime

    def model_dump(self) -> dict:
        return {
            "name": self.name,
            "normalizedName": self.normalized_name,
            "createdAt": self.created_at.isoformat(),
        }


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
"""


def _domain_services() -> str:
    return """import re

from app.domain.models import DemoItem, utc_now


def build_demo_item(name: str) -> DemoItem:
    normalized = re.sub(r"[^a-z0-9-]+", "-", name.lower()).strip("-")
    return DemoItem(name=name, normalized_name=normalized or "item", created_at=utc_now())
"""


def _application_use_cases() -> str:
    return """from app.domain.models import DemoItem
from app.domain.services import build_demo_item


def create_demo_item(name: str) -> DemoItem:
    return build_demo_item(name)
"""


def _health_service(context: dict[str, object]) -> str:
    imports = ["from app.config import settings"]
    checks = [
        '        "service": settings.service_name,',
        '        "businessPlatform": settings.business_platform_key,',
        '        "namespace": settings.business_platform_namespace,',
    ]
    if "redis" in context["middleware"]:
        imports.append("from app.infrastructure.redis_client import check_redis")
        checks.append('        "redis": ping_redis(),')
    if "postgresql" in context["middleware"]:
        imports.append("from app.infrastructure.postgres_repository import check_postgres")
        checks.append('        "postgresql": ping_postgres(),')
    body = "\n".join(imports)
    if "redis" in context["middleware"]:
        body += "\n\n\ndef ping_redis() -> dict:\n    return check_redis()"
    if "postgresql" in context["middleware"]:
        body += "\n\n\ndef ping_postgres() -> dict:\n    return check_postgres()"
    return body + "\n\n\ndef collect_health():\n    return {\n" + "\n".join(checks) + "\n    }\n"


def _redis_client() -> str:
    return """from redis import Redis

from app.config import settings


def check_redis() -> dict:
    try:
        client = Redis.from_url(settings.redis_url, socket_connect_timeout=1)
        return {"ok": bool(client.ping()), "url": settings.redis_url}
    except Exception as exc:
        return {"ok": False, "url": settings.redis_url, "error": str(exc)}
"""


def _postgres_repository() -> str:
    return """import psycopg

from app.config import settings


def check_postgres() -> dict:
    try:
        with psycopg.connect(settings.postgres_dsn, connect_timeout=1) as conn:
            with conn.cursor() as cursor:
                cursor.execute("select 1")
                ok = cursor.fetchone()[0] == 1
        return {"ok": ok}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
"""


def _postgres_init_sql() -> str:
    return """create table if not exists demo_items (
  id bigserial primary key,
  name varchar(128) not null,
  created_at timestamp default current_timestamp
);
"""


def _api_tests(context: dict[str, object]) -> str:
    return f"""from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["service"] == "{context['service_key']}"


def test_create_demo_item():
    response = client.post("/api/v1/items/Demo Item")
    assert response.status_code == 200
    payload = response.json()
    assert payload["name"] == "Demo Item"
    assert payload["normalizedName"] == "demo-item"
"""


def _k8s_namespace(context: dict[str, object]) -> str:
    return f"""apiVersion: v1
kind: Namespace
metadata:
  name: {context['k8s_namespace']}
  labels:
    business-platform: {context['business_platform_key']}
    source-env: {context['source_env']}
"""


def _k8s_deployment(context: dict[str, object]) -> str:
    service_key = context["service_key"]
    return f"""apiVersion: apps/v1
kind: Deployment
metadata:
  name: {service_key}
  namespace: {context['k8s_namespace']}
  labels:
    business-platform: {context['business_platform_key']}
    source-env: {context['source_env']}
spec:
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0
  replicas: 1
  selector:
    matchLabels:
      app: {service_key}
  template:
    metadata:
      labels:
        app: {service_key}
        business-platform: {context['business_platform_key']}
        source-env: {context['source_env']}
    spec:
      securityContext:
        runAsNonRoot: true
        seccompProfile:
          type: RuntimeDefault
      containers:
        - name: {service_key}
          image: {context['image']}:latest
          imagePullPolicy: IfNotPresent
          securityContext:
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: false
            capabilities:
              drop: ["ALL"]
          ports:
            - containerPort: {context['port']}
          envFrom:
            - configMapRef:
                name: {service_key}-config
            - secretRef:
                name: {service_key}-secret
          readinessProbe:
            httpGet:
              path: /health
              port: {context['port']}
            initialDelaySeconds: 5
            periodSeconds: 10
          livenessProbe:
            httpGet:
              path: /health
              port: {context['port']}
            initialDelaySeconds: 20
            periodSeconds: 20
          resources:
            requests:
              cpu: 100m
              memory: 128Mi
            limits:
              cpu: 500m
              memory: 512Mi
"""


def _k8s_service(context: dict[str, object]) -> str:
    return f"""apiVersion: v1
kind: Service
metadata:
  name: {context['service_key']}
  namespace: {context['k8s_namespace']}
  labels:
    business-platform: {context['business_platform_key']}
    source-env: {context['source_env']}
spec:
  selector:
    app: {context['service_key']}
  ports:
    - name: http
      port: 80
      targetPort: {context['port']}
"""


def _k8s_ingress(context: dict[str, object]) -> str:
    return f"""apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: {context['service_key']}
  namespace: {context['k8s_namespace']}
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /
spec:
  rules:
    - host: __REPLACE_WITH_HOST__
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: {context['service_key']}
                port:
                  number: 80
"""


def _k8s_configmap(context: dict[str, object]) -> str:
    lines = [
        "apiVersion: v1",
        "kind: ConfigMap",
        "metadata:",
        f"  name: {context['service_key']}-config",
        f"  namespace: {context['k8s_namespace']}",
        "data:",
        f"  SERVICE_NAME: {context['service_key']}",
        f"  BUSINESS_PLATFORM_KEY: {context['business_platform_key']}",
        f"  BUSINESS_PLATFORM_NAMESPACE: {context['business_platform_namespace']}",
        f"  SOURCE_ENV: {context['source_env']}",
        f"  APP_PORT: \"{context['port']}\"",
        "  LOG_LEVEL: INFO",
    ]
    if "redis" in context["middleware"]:
        lines.append("  REDIS_URL: redis://redis:6379/0")
    return "\n".join(lines) + "\n"


def _k8s_secret(context: dict[str, object]) -> str:
    lines = [
        "apiVersion: v1",
        "kind: Secret",
        "metadata:",
        f"  name: {context['service_key']}-secret",
        f"  namespace: {context['k8s_namespace']}",
        "type: Opaque",
        "stringData:",
    ]
    if "postgresql" in context["middleware"]:
        lines.append("  POSTGRES_DSN: postgresql://app:__REPLACE_WITH_POSTGRES_PASSWORD__@postgresql:5432/app")
    else:
        lines.append("  PLACEHOLDER: replace-me")
    return "\n".join(lines) + "\n"


def _helm_chart(context: dict[str, object]) -> str:
    return f"""apiVersion: v2
name: {context['service_key']}
description: Helm chart for {context['service_name']}
type: application
version: 0.1.0
appVersion: "0.1.0"
"""


def _helm_values(context: dict[str, object]) -> str:
    repository, tag = str(context["image"]), "latest"
    lines = [
        "replicaCount: 1",
        "",
        "image:",
        f"  repository: {repository}",
        f"  tag: {tag}",
        "  pullPolicy: IfNotPresent",
        "",
        "service:",
        "  type: ClusterIP",
        "  port: 80",
        f"  targetPort: {context['port']}",
        "",
        "ingress:",
        "  enabled: false",
        "  className: nginx",
        "  host: example.local",
        "",
        "env:",
        f"  SERVICE_NAME: {context['service_key']}",
        f"  BUSINESS_PLATFORM_KEY: {context['business_platform_key']}",
        f"  BUSINESS_PLATFORM_NAMESPACE: {context['business_platform_namespace']}",
        f"  SOURCE_ENV: {context['source_env']}",
        f"  APP_PORT: \"{context['port']}\"",
        "  LOG_LEVEL: INFO",
    ]
    if "redis" in context["middleware"]:
        lines.append("  REDIS_URL: redis://redis:6379/0")
    lines.extend(
        [
            "",
            "secretEnv:",
            "  POSTGRES_DSN: postgresql://app:__REPLACE_WITH_POSTGRES_PASSWORD__@postgresql:5432/app" if "postgresql" in context["middleware"] else "  PLACEHOLDER: replace-me",
            "",
            "resources:",
            "  requests:",
            "    cpu: 100m",
            "    memory: 128Mi",
            "  limits:",
            "    cpu: 500m",
            "    memory: 512Mi",
        ]
    )
    return "\n".join(lines) + "\n"


def _helm_helpers(context: dict[str, object]) -> str:
    return f"""{{{{- define "{context['service_key']}.name" -}}}}
{context['service_key']}
{{{{- end -}}}}
"""


def _helm_deployment(context: dict[str, object]) -> str:
    return f"""apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{{{ include "{context['service_key']}.name" . }}}}
  labels:
    app.kubernetes.io/name: {{{{ include "{context['service_key']}.name" . }}}}
    business-platform: {context['business_platform_key']}
    source-env: {context['source_env']}
spec:
  replicas: {{{{ .Values.replicaCount }}}}
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0
  selector:
    matchLabels:
      app.kubernetes.io/name: {{{{ include "{context['service_key']}.name" . }}}}
  template:
    metadata:
      labels:
        app.kubernetes.io/name: {{{{ include "{context['service_key']}.name" . }}}}
        business-platform: {context['business_platform_key']}
        source-env: {context['source_env']}
    spec:
      securityContext:
        runAsNonRoot: true
        seccompProfile:
          type: RuntimeDefault
      containers:
        - name: {{{{ include "{context['service_key']}.name" . }}}}
          image: "{{{{ .Values.image.repository }}}}:{{{{ .Values.image.tag }}}}"
          imagePullPolicy: {{{{ .Values.image.pullPolicy }}}}
          securityContext:
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: false
            capabilities:
              drop: ["ALL"]
          ports:
            - containerPort: {{{{ .Values.service.targetPort }}}}
          envFrom:
            - configMapRef:
                name: {{{{ include "{context['service_key']}.name" . }}}}-config
            - secretRef:
                name: {{{{ include "{context['service_key']}.name" . }}}}-secret
          readinessProbe:
            httpGet:
              path: /health
              port: {{{{ .Values.service.targetPort }}}}
            initialDelaySeconds: 5
            periodSeconds: 10
          livenessProbe:
            httpGet:
              path: /health
              port: {{{{ .Values.service.targetPort }}}}
            initialDelaySeconds: 20
            periodSeconds: 20
          resources:
{{{{ toYaml .Values.resources | indent 12 }}}}
"""


def _helm_service(context: dict[str, object]) -> str:
    return f"""apiVersion: v1
kind: Service
metadata:
  name: {{{{ include "{context['service_key']}.name" . }}}}
spec:
  type: {{{{ .Values.service.type }}}}
  selector:
    app.kubernetes.io/name: {{{{ include "{context['service_key']}.name" . }}}}
  ports:
    - name: http
      port: {{{{ .Values.service.port }}}}
      targetPort: {{{{ .Values.service.targetPort }}}}
"""


def _helm_configmap(context: dict[str, object]) -> str:
    return f"""apiVersion: v1
kind: ConfigMap
metadata:
  name: {{{{ include "{context['service_key']}.name" . }}}}-config
data:
{{{{- range $key, $value := .Values.env }}}}
  {{{{ $key }}}}: {{{{ $value | quote }}}}
{{{{- end }}}}
"""


def _helm_secret(context: dict[str, object]) -> str:
    return f"""apiVersion: v1
kind: Secret
metadata:
  name: {{{{ include "{context['service_key']}.name" . }}}}-secret
type: Opaque
stringData:
{{{{- range $key, $value := .Values.secretEnv }}}}
  {{{{ $key }}}}: {{{{ $value | quote }}}}
{{{{- end }}}}
"""


def _helm_ingress(context: dict[str, object]) -> str:
    return f"""{{{{- if .Values.ingress.enabled }}}}
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: {{{{ include "{context['service_key']}.name" . }}}}
spec:
  ingressClassName: {{{{ .Values.ingress.className }}}}
  rules:
    - host: {{{{ .Values.ingress.host }}}}
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: {{{{ include "{context['service_key']}.name" . }}}}
                port:
                  number: {{{{ .Values.service.port }}}}
{{{{- end }}}}
"""
