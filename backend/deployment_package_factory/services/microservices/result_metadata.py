from __future__ import annotations


def image_ref(request) -> str:
    return f"{request.image_registry.rstrip('/')}/{request.image_namespace.strip('/')}/{request.service_key}"


def git_repository_url(request) -> str:
    group = request.git_group.strip("/")
    path = f"{group}/{request.service_key}" if group else request.service_key
    base_url = request.git_base_url.rstrip("/")
    return f"{base_url}/{path}.git" if base_url else path


def jenkins_job(request) -> str:
    folder = request.jenkins_folder.strip("/")
    path = f"{folder}/{request.service_key}" if folder else request.service_key
    base_url = request.jenkins_base_url.rstrip("/")
    return f"{base_url}/job/{path.replace('/', '/job/')}" if base_url else path


def build_command(request) -> str:
    return f"./build.sh {image_ref(request)}:dev"


def deploy_command(request) -> str:
    return f"./deploy.sh {image_ref(request)}:dev"
