from __future__ import annotations

import json
import shutil
import subprocess
from time import perf_counter
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from deployment_package_factory.services.microservices.git_providers import GitProviderError, resolve_git_client
from deployment_package_factory.services.microservices.result_metadata import git_repository_url, jenkins_job
from deployment_package_factory.services.settings import SystemSettings


def prepare_microservice_delivery(request, result, settings: SystemSettings, project_root: Path | None = None) -> dict[str, object]:
    steps = [
        _prepare_git_project(request, settings, project_root),
        _prepare_jenkins_job(request, settings),
    ]
    return {"status": _overall_status(steps), "steps": steps}


def refresh_delivery_status(delivery: dict[str, object], settings: SystemSettings) -> dict[str, object]:
    steps = list(delivery.get("steps", []))
    build_step = next((step for step in steps if step.get("name") == "jenkins-job" and step.get("target")), None)
    if not build_step or not settings.jenkins.base_url or not settings.jenkins.username or not settings.jenkins.password:
        return {"status": delivery.get("status", "unknown"), "steps": steps, "build": {"status": "unknown", "message": "Jenkins 构建地址或凭据不可用。"}}
    try:
        build = JenkinsClient(settings.jenkins.base_url, settings.jenkins.username, settings.jenkins.password).read_build_status(str(build_step["target"]))
    except DeliveryError as exc:
        build = {"status": "unknown", "message": str(exc), "url": str(build_step["target"])}
    return {"status": _delivery_status_with_build(str(delivery.get("status", "unknown")), build), "steps": steps, "build": build}


def _prepare_git_project(request, settings: SystemSettings, project_root: Path | None) -> dict[str, str]:
    started = perf_counter()
    target = git_repository_url(request)
    if not settings.git.base_url:
        return _step("git-project", "skipped", "config", "检查 Git 配置", "Git 地址未配置，已生成本地项目包。", target, started, "在设置页填写 Git 地址和 Token 后重新注册。")
    if not settings.git.token:
        return _step("git-project", "pending", "config", "检查 Git Token", "Git Token 未配置，无法自动创建远程项目。", target, started, "在设置页填写 Git 访问 Token。")
    try:
        remote_url = resolve_git_client(settings).ensure_project(request.git_group, request.service_key)
        if project_root and project_root.exists():
            _push_initial_commit(project_root, remote_url, settings.git.token, _git_push_username(settings))
        return _step("git-project", "ready", "provision", "创建 Git 项目并推送初始化代码", "Git 项目已创建并推送初始化代码。", remote_url, started)
    except (DeliveryError, GitProviderError) as exc:
        return _step("git-project", "failed", "provision", "创建 Git 项目或推送代码", str(exc), target, started, "检查 Git 地址、Token 权限、默认分组是否存在。")


def _prepare_jenkins_job(request, settings: SystemSettings) -> dict[str, str]:
    started = perf_counter()
    target = jenkins_job(request)
    if not settings.jenkins.base_url:
        return _step("jenkins-job", "skipped", "config", "检查 Jenkins 配置", "Jenkins 地址未配置，已生成 Jenkinsfile。", target, started, "在设置页填写 Jenkins 地址和凭据。")
    if not settings.jenkins.username or not settings.jenkins.password:
        return _step("jenkins-job", "pending", "config", "检查 Jenkins 凭据", "Jenkins 账号或 Token 未配置，无法自动创建 Job。", target, started, "在设置页填写 Jenkins 用户名和 Token。")
    try:
        client = JenkinsClient(settings.jenkins.base_url, settings.jenkins.username, settings.jenkins.password)
        job_path = client.ensure_pipeline_job(
            request.jenkins_folder,
            request.service_key,
            git_repository_url(request),
        )
        build_target = client.trigger_build(job_path)
        message = "Jenkins Pipeline Job 已创建或已存在，并已触发首次构建。"
        return _step("jenkins-job", "ready", "provision", "创建 Jenkins Job 并触发首次构建", message, build_target or target, started)
    except DeliveryError as exc:
        return _step("jenkins-job", "failed", "provision", "创建 Jenkins Job 或触发构建", str(exc), target, started, "检查 Jenkins 地址、账号 Token、文件夹权限和 Git 插件。")


class DeliveryError(RuntimeError):
    pass


class JenkinsClient:
    def __init__(self, base_url: str, username: str, token: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.auth = _basic_auth(username, token)

    def ensure_pipeline_job(self, folder: str, service_key: str, git_url: str) -> str:
        parent = "".join(f"/job/{quote(part)}" for part in folder.strip("/").split("/") if part)
        url = f"{self.base_url}{parent}/createItem?{urlencode({'name': service_key})}"
        xml = _pipeline_job_xml(git_url).encode("utf-8")
        headers = {"Authorization": self.auth, "Content-Type": "application/xml"}
        try:
            _bytes_request("POST", url, headers, xml)
        except DeliveryError as exc:
            if "400" not in str(exc):
                raise
        return f"{parent}/job/{quote(service_key)}"

    def trigger_build(self, job_path: str) -> str:
        url = f"{self.base_url}{job_path}/build"
        _bytes_request("POST", url, {"Authorization": self.auth}, None)
        return url

    def read_build_status(self, build_url: str) -> dict[str, object]:
        data = _json_request("GET", f"{build_url.rstrip('/')}/api/json", {"Authorization": self.auth})
        building = bool(data.get("building"))
        result = str(data.get("result") or "").lower()
        if building:
            status = "running"
        elif result == "success":
            status = "success"
        elif result:
            status = "failed"
        else:
            status = "queued"
        return {
            "status": status,
            "result": result or None,
            "building": building,
            "url": str(data.get("url") or build_url),
            "number": data.get("number"),
            "message": _build_message(status),
        }


def _push_initial_commit(project_root: Path, remote_url: str, token: str, username: str = "oauth2") -> None:
    if not shutil.which("git"):
        raise DeliveryError("Git 命令不可用，无法初始化推送。")
    _git(project_root, ["remote", "remove", "origin"], check=False)
    _git(project_root, ["remote", "add", "origin", remote_url])
    _git(project_root, ["-c", f"http.extraHeader=Authorization: {_basic_auth(username, token)}", "push", "-u", "origin", "main"])


def _git_push_username(settings: SystemSettings) -> str:
    provider = (settings.git.provider or "").strip().lower()
    base_url = settings.git.base_url.lower()
    if provider == "github" or "github.com" in base_url or "github." in base_url:
        return settings.git.username or "x-access-token"
    return settings.git.username or "oauth2"


def _git(project_root: Path, args: list[str], *, check: bool = True) -> None:
    result = subprocess.run(["git", *args], cwd=project_root, capture_output=True, text=True)
    if check and result.returncode != 0:
        raise DeliveryError((result.stderr or result.stdout or "git command failed").strip())


def _json_request(method: str, url: str, headers: dict[str, str], body: bytes | None = None) -> dict:
    payload = _bytes_request(method, url, headers, body)
    return json.loads(payload.decode("utf-8")) if payload else {}


def _bytes_request(method: str, url: str, headers: dict[str, str], body: bytes | None = None) -> bytes:
    try:
        with urlopen(Request(url, data=body, method=method, headers=headers), timeout=15) as response:
            return response.read()
    except HTTPError as exc:
        raise DeliveryError(f"HTTP {exc.code}: {exc.reason}") from exc
    except URLError as exc:
        raise DeliveryError(str(exc.reason)) from exc


def _basic_auth(username: str, token: str) -> str:
    import base64

    return "Basic " + base64.b64encode(f"{username}:{token}".encode("utf-8")).decode("ascii")


def _pipeline_job_xml(git_url: str) -> str:
    return f"""<flow-definition plugin="workflow-job">
  <definition class="org.jenkinsci.plugins.workflow.cps.CpsScmFlowDefinition">
    <scm class="hudson.plugins.git.GitSCM">
      <userRemoteConfigs><hudson.plugins.git.UserRemoteConfig><url>{git_url}</url></hudson.plugins.git.UserRemoteConfig></userRemoteConfigs>
      <branches><hudson.plugins.git.BranchSpec><name>*/main</name></hudson.plugins.git.BranchSpec></branches>
    </scm>
    <scriptPath>Jenkinsfile</scriptPath>
    <lightweight>true</lightweight>
  </definition>
</flow-definition>"""


def _step(name: str, status: str, phase: str, action: str, message: str, target: str, started: float, hint: str = "") -> dict[str, object]:
    return {
        "name": name,
        "status": status,
        "phase": phase,
        "action": action,
        "message": message,
        "target": target,
        "hint": hint,
        "retryable": status in {"failed", "pending"},
        "elapsedMs": round((perf_counter() - started) * 1000, 2),
    }


def _overall_status(steps: list[dict[str, object]]) -> str:
    statuses = {step["status"] for step in steps}
    if "failed" in statuses:
        return "failed"
    if "pending" in statuses:
        return "pending"
    if statuses == {"skipped"}:
        return "skipped"
    return "ready"


def _delivery_status_with_build(current: str, build: dict[str, object]) -> str:
    if build.get("status") == "failed":
        return "failed"
    if build.get("status") in {"queued", "running"}:
        return "running"
    if build.get("status") == "success" and current == "ready":
        return "success"
    return current


def _build_message(status: str) -> str:
    return {
        "queued": "Jenkins 构建已进入队列。",
        "running": "Jenkins 构建正在执行。",
        "success": "Jenkins 构建成功。",
        "failed": "Jenkins 构建失败。",
    }.get(status, "Jenkins 构建状态未知。")
