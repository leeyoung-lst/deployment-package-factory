from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from deployment_package_factory.services.microservices.result_metadata import git_repository_url, jenkins_job
from deployment_package_factory.services.settings import SystemSettings


def prepare_microservice_delivery(request, result, settings: SystemSettings, project_root: Path | None = None) -> dict[str, object]:
    steps = [
        _prepare_git_project(request, settings, project_root),
        _prepare_jenkins_job(request, settings),
    ]
    return {"status": _overall_status(steps), "steps": steps}


def _prepare_git_project(request, settings: SystemSettings, project_root: Path | None) -> dict[str, str]:
    target = git_repository_url(request)
    if not settings.git.base_url:
        return _step("git-project", "skipped", "Git 地址未配置，已生成本地项目包。", target)
    if not settings.git.token:
        return _step("git-project", "pending", "Git Token 未配置，无法自动创建远程项目。", target)
    try:
        remote_url = GitLabClient(settings.git.base_url, settings.git.token).ensure_project(request.git_group, request.service_key)
        if project_root and project_root.exists():
            _push_initial_commit(project_root, remote_url, settings.git.token)
        return _step("git-project", "ready", "Git 项目已创建并准备初始化代码。", remote_url)
    except DeliveryError as exc:
        return _step("git-project", "failed", str(exc), target)


def _prepare_jenkins_job(request, settings: SystemSettings) -> dict[str, str]:
    target = jenkins_job(request)
    if not settings.jenkins.base_url:
        return _step("jenkins-job", "skipped", "Jenkins 地址未配置，已生成 Jenkinsfile。", target)
    if not settings.jenkins.username or not settings.jenkins.password:
        return _step("jenkins-job", "pending", "Jenkins 账号或 Token 未配置，无法自动创建 Job。", target)
    try:
        JenkinsClient(settings.jenkins.base_url, settings.jenkins.username, settings.jenkins.password).ensure_pipeline_job(
            request.jenkins_folder,
            request.service_key,
            git_repository_url(request),
        )
        return _step("jenkins-job", "ready", "Jenkins Pipeline Job 已创建或已存在。", target)
    except DeliveryError as exc:
        return _step("jenkins-job", "failed", str(exc), target)


class DeliveryError(RuntimeError):
    pass


class GitLabClient:
    def __init__(self, base_url: str, token: str) -> None:
        self.api_base = f"{base_url.rstrip('/')}/api/v4"
        self.token = token

    def ensure_project(self, group: str, service_key: str) -> str:
        namespace_id = self._group_id(group)
        payload = {"name": service_key, "path": service_key, "visibility": "private"}
        if namespace_id is not None:
            payload["namespace_id"] = namespace_id
        try:
            data = self._request("POST", "/projects", payload)
        except DeliveryError as exc:
            if "409" not in str(exc):
                raise
            data = self._request("GET", f"/projects/{quote(f'{group}/{service_key}', safe='')}")
        return str(data.get("http_url_to_repo") or data.get("web_url") or f"{group}/{service_key}")

    def _group_id(self, group: str) -> int | None:
        if not group:
            return None
        data = self._request("GET", f"/groups/{quote(group, safe='')}")
        return int(data["id"])

    def _request(self, method: str, path: str, payload: dict | None = None) -> dict:
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        headers = {"PRIVATE-TOKEN": self.token, "Content-Type": "application/json"}
        return _json_request(method, f"{self.api_base}{path}", headers, body)


class JenkinsClient:
    def __init__(self, base_url: str, username: str, token: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.auth = _basic_auth(username, token)

    def ensure_pipeline_job(self, folder: str, service_key: str, git_url: str) -> None:
        parent = "".join(f"/job/{quote(part)}" for part in folder.strip("/").split("/") if part)
        url = f"{self.base_url}{parent}/createItem?{urlencode({'name': service_key})}"
        xml = _pipeline_job_xml(git_url).encode("utf-8")
        headers = {"Authorization": self.auth, "Content-Type": "application/xml"}
        try:
            _bytes_request("POST", url, headers, xml)
        except DeliveryError as exc:
            if "400" not in str(exc):
                raise


def _push_initial_commit(project_root: Path, remote_url: str, token: str) -> None:
    if not shutil.which("git"):
        raise DeliveryError("Git 命令不可用，无法初始化推送。")
    _git(project_root, ["remote", "remove", "origin"], check=False)
    _git(project_root, ["remote", "add", "origin", remote_url])
    _git(project_root, ["-c", f"http.extraHeader=Authorization: {_basic_auth('oauth2', token)}", "push", "-u", "origin", "main"])


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


def _step(name: str, status: str, message: str, target: str = "") -> dict[str, str]:
    return {"name": name, "status": status, "message": message, "target": target}


def _overall_status(steps: list[dict[str, str]]) -> str:
    statuses = {step["status"] for step in steps}
    if "failed" in statuses:
        return "failed"
    if "pending" in statuses:
        return "pending"
    if statuses == {"skipped"}:
        return "skipped"
    return "ready"
