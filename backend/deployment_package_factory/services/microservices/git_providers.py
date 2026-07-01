from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


class GitProviderError(RuntimeError):
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
        except GitProviderError as exc:
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


class GitHubClient:
    def __init__(self, base_url: str, token: str) -> None:
        self.web_base = base_url.rstrip("/") or "https://github.com"
        self.api_base = _github_api_base(self.web_base)
        self.token = token

    def ensure_project(self, owner: str, service_key: str) -> str:
        if not owner:
            raise GitProviderError("GitHub owner is required.")
        path = f"{owner}/{service_key}"
        payload = {"name": service_key, "private": True, "auto_init": False}
        try:
            data = self._request("POST", f"/orgs/{quote(owner, safe='')}/repos", payload)
        except GitProviderError as org_exc:
            if "404" in str(org_exc):
                data = self._create_user_repo(path, payload)
            elif "422" in str(org_exc):
                data = self._request("GET", f"/repos/{quote(path, safe='/')}")
            else:
                raise
        return str(data.get("clone_url") or data.get("html_url") or f"{self.web_base}/{path}.git")

    def _create_user_repo(self, path: str, payload: dict) -> dict:
        try:
            return self._request("POST", "/user/repos", payload)
        except GitProviderError as user_exc:
            if "422" not in str(user_exc):
                raise
            return self._request("GET", f"/repos/{quote(path, safe='/')}")

    def _request(self, method: str, path: str, payload: dict | None = None) -> dict:
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        return _json_request(method, f"{self.api_base}{path}", headers, body)


def resolve_git_client(settings):
    provider = _resolve_provider(settings.git.provider, settings.git.base_url)
    if provider == "github":
        return GitHubClient(settings.git.base_url, settings.git.token)
    return GitLabClient(settings.git.base_url, settings.git.token)


def _resolve_provider(provider: str, base_url: str) -> str:
    normalized = (provider or "").strip().lower()
    if "github." in base_url or "github.com" in base_url:
        return "github"
    if normalized in {"github", "gitlab"}:
        return normalized
    return "gitlab"


def _github_api_base(base_url: str) -> str:
    if base_url in {"https://github.com", "http://github.com"}:
        return "https://api.github.com"
    return f"{base_url.rstrip('/')}/api/v3"


def _json_request(method: str, url: str, headers: dict[str, str], body: bytes | None = None) -> dict:
    payload = _bytes_request(method, url, headers, body)
    return json.loads(payload.decode("utf-8")) if payload else {}


def _bytes_request(method: str, url: str, headers: dict[str, str], body: bytes | None = None) -> bytes:
    try:
        with urlopen(Request(url, data=body, method=method, headers=headers), timeout=15) as response:
            return response.read()
    except HTTPError as exc:
        raise GitProviderError(f"HTTP {exc.code}: {exc.reason}") from exc
    except URLError as exc:
        raise GitProviderError(str(exc.reason)) from exc
