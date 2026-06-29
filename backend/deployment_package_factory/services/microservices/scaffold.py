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


DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[4] / "data" / "microservice-projects"
SUPPORTED_TECH_STACKS = {
    "python-fastapi": "Python FastAPI",
}
SUPPORTED_MIDDLEWARE = {
    "redis": "Redis",
    "postgresql": "PostgreSQL",
}


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
    git_group: str = Field(default="business-services", alias="gitGroup")
    image_registry: str = Field(default="registry.local", alias="imageRegistry")
    image_namespace: str = Field(default="business", alias="imageNamespace")
    k8s_namespace: str = Field(default="", alias="k8sNamespace")

    @field_validator("service_key")
    @classmethod
    def validate_service_key(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not re.fullmatch(r"[a-z][a-z0-9-]{1,62}", normalized):
            raise ValueError("serviceKey must start with a letter and contain only lowercase letters, numbers, and hyphens")
        return normalized

    @field_validator("tech_stack")
    @classmethod
    def validate_tech_stack(cls, value: str) -> str:
        if value not in SUPPORTED_TECH_STACKS:
            raise ValueError(f"Unsupported techStack: {value}")
        return value

    @field_validator("project_kind")
    @classmethod
    def validate_project_kind(cls, value: str) -> str:
        if value != "backend":
            raise ValueError("Level 0 supports backend projects only")
        return value

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
        projectKinds=[{"key": "backend", "name": "后端微服务"}],
        techStacks=[{"key": key, "name": name} for key, name in SUPPORTED_TECH_STACKS.items()],
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

    rendered_files = _render_python_fastapi(request)
    for rendered_file in rendered_files:
        _write_file(project_root / Path(*rendered_file.path.parts), rendered_file.content, rendered_file.executable)
    _initialize_git(project_root)

    artifact_name = f"{request.service_key}-{project_id}.tar.gz"
    artifact_path = artifact_dir / artifact_name
    with tarfile.open(artifact_path, "w:gz") as tar:
        tar.add(project_root, arcname=request.service_key)
    digest = _file_sha256(artifact_path)

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
    )


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
        RenderedFile(PurePosixPath("src/app/__init__.py"), ""),
        RenderedFile(PurePosixPath("src/app/main.py"), _fastapi_main(context)),
        RenderedFile(PurePosixPath("src/app/config.py"), _fastapi_config(context)),
        RenderedFile(PurePosixPath("src/app/api/__init__.py"), ""),
        RenderedFile(PurePosixPath("src/app/api/routes.py"), _fastapi_routes(context)),
        RenderedFile(PurePosixPath("src/app/services/__init__.py"), ""),
        RenderedFile(PurePosixPath("src/app/services/health.py"), _health_service(context)),
        RenderedFile(PurePosixPath("deploy/k8s/deployment.yaml"), _k8s_deployment(context)),
        RenderedFile(PurePosixPath("deploy/k8s/service.yaml"), _k8s_service(context)),
        RenderedFile(PurePosixPath("deploy/k8s/configmap.yaml"), _k8s_configmap(context)),
        RenderedFile(PurePosixPath("deploy/k8s/secret.template.yaml"), _k8s_secret(context)),
    ]
    if "redis" in request.middleware:
        files.append(RenderedFile(PurePosixPath("src/app/services/redis_client.py"), _redis_client()))
    if "postgresql" in request.middleware:
        files.extend(
            [
                RenderedFile(PurePosixPath("src/app/repositories/__init__.py"), ""),
                RenderedFile(PurePosixPath("src/app/repositories/postgres.py"), _postgres_repository()),
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
    return "\n".join(lines) + "\n"


def _readme(context: dict[str, object]) -> str:
    middleware = ", ".join(context["middleware"]) or "none"
    return f"""# {context['service_name']}

{context['description']}

## Local development

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
cp .env.template .env
uvicorn app.main:app --reload --host 0.0.0.0 --port {context['port']}
```

## Build image

```bash
./build.sh {context['image']}:dev
```

## Middleware

Enabled middleware: {middleware}

## Business platform

- Platform: {context['business_platform_name']} ({context['business_platform_key']})
- Profile: {context['business_platform_profile'] or 'default'}
- Namespace: {context['business_platform_namespace']}
- Source environment: {context['source_env']}

## Kubernetes

```bash
kubectl apply -f deploy/k8s/configmap.yaml
kubectl apply -f deploy/k8s/secret.template.yaml
kubectl apply -f deploy/k8s/deployment.yaml
kubectl apply -f deploy/k8s/service.yaml
```
"""


def _requirements(context: dict[str, object]) -> str:
    dependencies = ["fastapi>=0.115.0", "uvicorn[standard]>=0.30.0", "pydantic-settings>=2.5.0"]
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
EXPOSE {context['port']}
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "{context['port']}"]
"""


def _jenkinsfile(context: dict[str, object]) -> str:
    return f"""pipeline {{
  agent any
  environment {{
    IMAGE = "{context['image']}:${{env.BUILD_NUMBER}}"
    K8S_NAMESPACE = "{context['k8s_namespace']}"
  }}
  stages {{
    stage('Install') {{
      steps {{
        sh 'python -m pip install -r requirements.txt'
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
        sh 'kubectl -n $K8S_NAMESPACE set image deployment/{context['service_key']} {context['service_key']}=$IMAGE || kubectl apply -f deploy/k8s'
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


def _fastapi_main(context: dict[str, object]) -> str:
    return f"""from fastapi import FastAPI

from app.api.routes import router
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
    imports = ["from fastapi import APIRouter", "", "from app.services.health import collect_health"]
    body = [
        "",
        "router = APIRouter(prefix=\"/api\")",
        "",
        "",
        "@router.get(\"/hello\")",
        "def hello():",
        f"    return {{\"message\": \"hello from {context['service_key']}\"}}",
        "",
        "",
        "@router.get(\"/runtime\")",
        "def runtime():",
        "    return collect_health()",
    ]
    return "\n".join(imports + body) + "\n"


def _health_service(context: dict[str, object]) -> str:
    imports = ["from app.config import settings"]
    checks = [
        '        "service": settings.service_name,',
        '        "businessPlatform": settings.business_platform_key,',
        '        "namespace": settings.business_platform_namespace,',
    ]
    if "redis" in context["middleware"]:
        imports.append("from app.services.redis_client import ping_redis")
        checks.append('        "redis": ping_redis(),')
    if "postgresql" in context["middleware"]:
        imports.append("from app.repositories.postgres import ping_postgres")
        checks.append('        "postgresql": ping_postgres(),')
    return "\n".join(imports) + "\n\n\ndef collect_health():\n    return {\n" + "\n".join(checks) + "\n    }\n"


def _redis_client() -> str:
    return """from redis import Redis

from app.config import settings


def ping_redis() -> bool:
    client = Redis.from_url(settings.redis_url, socket_connect_timeout=1)
    return bool(client.ping())
"""


def _postgres_repository() -> str:
    return """import psycopg

from app.config import settings


def ping_postgres() -> bool:
    with psycopg.connect(settings.postgres_dsn, connect_timeout=1) as conn:
        with conn.cursor() as cursor:
            cursor.execute("select 1")
            return cursor.fetchone()[0] == 1
"""


def _postgres_init_sql() -> str:
    return """create table if not exists demo_items (
  id bigserial primary key,
  name varchar(128) not null,
  created_at timestamp default current_timestamp
);
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
      containers:
        - name: {service_key}
          image: {context['image']}:latest
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
