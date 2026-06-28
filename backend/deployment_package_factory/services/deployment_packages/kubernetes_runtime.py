from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


DPF_LABEL_PREFIX = "deployment-package-factory.local-ai"
ENV_LABEL = f"{DPF_LABEL_PREFIX}/environment"
NAMESPACE_TYPE_LABEL = f"{DPF_LABEL_PREFIX}/namespace-type"
BUSINESS_KEY_LABEL = f"{DPF_LABEL_PREFIX}/business-key"
STATUS_LABEL = f"{DPF_LABEL_PREFIX}/status"
BUSINESS_NAME_ANNOTATION = f"{DPF_LABEL_PREFIX}/business-name"
BUSINESS_PROFILE_ANNOTATION = f"{DPF_LABEL_PREFIX}/business-profile"
MANAGED_BY_LABEL = "app.kubernetes.io/managed-by"
MANAGED_BY_VALUE = "deployment-package-factory"
LOCAL_AI_ENV_LABEL = "local-ai.io/environment"


class KubernetesRuntimeError(RuntimeError):
    pass


@dataclass(frozen=True)
class RegisteredBusinessPlatform:
    key: str
    name: str
    profile: str
    namespace: str
    source_env: str
    status: str = "active"


def source_env_namespaces(source_env: str, business_namespaces: list[str] | None = None) -> list[str]:
    normalized_env = source_env.strip().lower()
    env_key = re.sub(r"[^A-Za-z0-9]+", "_", source_env.strip().upper())
    raw = os.getenv(f"DEPLOYMENT_PACKAGE_SOURCE_NAMESPACES_{env_key}", "").strip()
    if not raw:
        raw = os.getenv("DEPLOYMENT_PACKAGE_SOURCE_NAMESPACES", "").strip()
    if not raw:
        defaults = {
            "dev": "local-ai-dev",
            "test": "local-ai",
        }
        raw = defaults.get(normalized_env, "")
    namespaces = [item.strip() for item in raw.split(",") if item.strip()]
    try:
        namespaces.extend(_list_namespaces_by_label(LOCAL_AI_ENV_LABEL, normalized_env))
        namespaces.extend(_list_namespaces_by_label(ENV_LABEL, normalized_env))
        namespaces.extend(business_namespaces or [])
        if business_namespaces is None:
            namespaces.extend(item.namespace for item in list_registered_business_platforms(source_env))
    except KubernetesRuntimeError:
        pass
    return list(dict.fromkeys(namespaces))


def business_namespace(source_env: str, business_key: str, profile: str = "") -> str:
    profile_label = _dns_label(profile) if profile else ""
    suffix = f"-{profile_label}" if profile_label else ""
    return f"{_dns_label(source_env)}-biz-{_dns_label(business_key)}{suffix}"


def list_registered_business_platforms(source_env: str | None = None, *, include_disabled: bool = False) -> list[RegisteredBusinessPlatform]:
    token = _service_account_token()
    if not token:
        return []
    selector_parts = [
        f"{MANAGED_BY_LABEL}={MANAGED_BY_VALUE}",
        f"{NAMESPACE_TYPE_LABEL}=business",
    ]
    if source_env:
        selector_parts.append(f"{ENV_LABEL}={source_env}")
    payload = _request_json("GET", f"/api/v1/namespaces?labelSelector={quote(','.join(selector_parts), safe='=,./-')}", token)
    result: list[RegisteredBusinessPlatform] = []
    for item in payload.get("items", []):
        metadata = item.get("metadata") or {}
        labels = metadata.get("labels") or {}
        annotations = metadata.get("annotations") or {}
        status = labels.get(STATUS_LABEL) or "active"
        if status == "disabled" and not include_disabled:
            continue
        key = labels.get(BUSINESS_KEY_LABEL) or _business_key_from_namespace(metadata.get("name", ""))
        if not key:
            continue
        result.append(
            RegisteredBusinessPlatform(
                key=key,
                name=annotations.get(BUSINESS_NAME_ANNOTATION) or key.upper(),
                profile=annotations.get(BUSINESS_PROFILE_ANNOTATION) or "",
                namespace=metadata.get("name", ""),
                source_env=labels.get(ENV_LABEL) or "",
                status=status,
            )
        )
    return sorted(result, key=lambda item: (item.source_env, item.key, item.namespace))


def register_business_platform(source_env: str, key: str, name: str = "", profile: str = "") -> RegisteredBusinessPlatform:
    normalized_env = _dns_label(source_env)
    normalized_key = _dns_label(key)
    namespace = business_namespace(normalized_env, normalized_key, profile)
    token = _require_service_account_token()
    existing = _get_namespace(namespace, token)
    labels = _business_namespace_labels(normalized_env, normalized_key, "active")
    annotations = _business_namespace_annotations(name or normalized_key.upper(), profile)
    if existing:
        _patch_namespace_metadata(namespace, labels, annotations, token)
    else:
        _create_namespace(namespace, labels, annotations, token)
    return RegisteredBusinessPlatform(
        key=normalized_key,
        name=name or normalized_key.upper(),
        profile=profile,
        namespace=namespace,
        source_env=normalized_env,
        status="active",
    )


def disable_business_platform(source_env: str, key: str, profile: str = "") -> RegisteredBusinessPlatform:
    normalized_env = _dns_label(source_env)
    normalized_key = _dns_label(key)
    namespace = business_namespace(normalized_env, normalized_key, profile)
    token = _require_service_account_token()
    existing = _get_namespace(namespace, token)
    if not existing:
        raise KubernetesRuntimeError(f"Business namespace {namespace!r} does not exist.")
    labels = ((existing.get("metadata") or {}).get("labels") or {}).copy()
    if labels.get(NAMESPACE_TYPE_LABEL) != "business" or labels.get(BUSINESS_KEY_LABEL) != normalized_key:
        raise KubernetesRuntimeError(f"Namespace {namespace!r} is not a registered business platform.")
    labels[STATUS_LABEL] = "disabled"
    annotations = ((existing.get("metadata") or {}).get("annotations") or {}).copy()
    _patch_namespace_metadata(namespace, labels, annotations, token)
    return RegisteredBusinessPlatform(
        key=normalized_key,
        name=annotations.get(BUSINESS_NAME_ANNOTATION) or normalized_key.upper(),
        profile=annotations.get(BUSINESS_PROFILE_ANNOTATION) or "",
        namespace=namespace,
        source_env=normalized_env,
        status="disabled",
    )


def _list_namespaces_by_label(label_key: str, label_value: str) -> list[str]:
    token = _service_account_token()
    if not token:
        return []
    selector = quote(f"{label_key}={label_value}", safe="=,./-")
    payload = _request_json("GET", f"/api/v1/namespaces?labelSelector={selector}", token)
    return [
        str((item.get("metadata") or {}).get("name") or "")
        for item in payload.get("items", [])
        if (item.get("metadata") or {}).get("name")
    ]


def read_kubernetes_pods(namespace: str, token: str | None = None) -> dict:
    access_token = token or _service_account_token()
    if not access_token:
        return {}
    try:
        return _request_json("GET", f"/api/v1/namespaces/{quote(namespace, safe='')}/pods", access_token)
    except KubernetesRuntimeError:
        return {}


def create_image_export_pod(
    *,
    namespace: str,
    name: str,
    node_name: str,
    image: str,
    command: list[str],
    data_claim_name: str,
    data_mount_path: str,
    containerd_socket: str,
) -> dict:
    token = _require_service_account_token()
    return _request_json(
        "POST",
        f"/api/v1/namespaces/{quote(namespace, safe='')}/pods",
        token,
        body={
            "apiVersion": "v1",
            "kind": "Pod",
            "metadata": {
                "name": name,
                "labels": {
                    MANAGED_BY_LABEL: MANAGED_BY_VALUE,
                    "app.kubernetes.io/name": MANAGED_BY_VALUE,
                    "app.kubernetes.io/component": "image-export-helper",
                },
            },
            "spec": {
                "restartPolicy": "Never",
                "serviceAccountName": MANAGED_BY_VALUE,
                "nodeName": node_name,
                "containers": [
                    {
                        "name": "exporter",
                        "image": image,
                        "imagePullPolicy": "IfNotPresent",
                        "command": command,
                        "securityContext": {
                            "privileged": True,
                            "runAsUser": 0,
                            "runAsGroup": 0,
                            "allowPrivilegeEscalation": True,
                        },
                        "volumeMounts": [
                            {"name": "data", "mountPath": data_mount_path},
                            {"name": "containerd-socket", "mountPath": containerd_socket, "readOnly": True},
                        ],
                    }
                ],
                "volumes": [
                    {"name": "data", "persistentVolumeClaim": {"claimName": data_claim_name}},
                    {"name": "containerd-socket", "hostPath": {"path": containerd_socket, "type": "Socket"}},
                ],
            },
        },
    )


def get_pod(namespace: str, name: str) -> dict | None:
    token = _require_service_account_token()
    try:
        return _request_json("GET", f"/api/v1/namespaces/{quote(namespace, safe='')}/pods/{quote(name, safe='')}", token)
    except KubernetesRuntimeError as exc:
        if "404" in str(exc):
            return None
        raise


def delete_pod(namespace: str, name: str) -> None:
    token = _require_service_account_token()
    try:
        _request_json("DELETE", f"/api/v1/namespaces/{quote(namespace, safe='')}/pods/{quote(name, safe='')}", token, body={})
    except KubernetesRuntimeError as exc:
        if "404" not in str(exc):
            raise


def _business_namespace_labels(source_env: str, key: str, status: str) -> dict[str, str]:
    return {
        MANAGED_BY_LABEL: MANAGED_BY_VALUE,
        ENV_LABEL: source_env,
        NAMESPACE_TYPE_LABEL: "business",
        BUSINESS_KEY_LABEL: key,
        STATUS_LABEL: status,
    }


def _business_namespace_annotations(name: str, profile: str) -> dict[str, str]:
    return {
        BUSINESS_NAME_ANNOTATION: name,
        BUSINESS_PROFILE_ANNOTATION: profile,
    }


def _get_namespace(namespace: str, token: str) -> dict | None:
    try:
        return _request_json("GET", f"/api/v1/namespaces/{quote(namespace, safe='')}", token)
    except KubernetesRuntimeError as exc:
        if "404" in str(exc):
            return None
        raise


def _create_namespace(namespace: str, labels: dict[str, str], annotations: dict[str, str], token: str) -> None:
    _request_json(
        "POST",
        "/api/v1/namespaces",
        token,
        body={
            "apiVersion": "v1",
            "kind": "Namespace",
            "metadata": {
                "name": namespace,
                "labels": labels,
                "annotations": annotations,
            },
        },
    )


def _patch_namespace_metadata(namespace: str, labels: dict[str, str], annotations: dict[str, str], token: str) -> None:
    _request_json(
        "PATCH",
        f"/api/v1/namespaces/{quote(namespace, safe='')}",
        token,
        body={"metadata": {"labels": labels, "annotations": annotations}},
        content_type="application/merge-patch+json",
    )


def _request_json(method: str, path: str, token: str, body: dict | None = None, content_type: str = "application/json") -> dict:
    base_url = os.getenv("KUBERNETES_SERVICE_HOST_URL", "https://kubernetes.default.svc").rstrip("/")
    ca_file = os.getenv("KUBERNETES_SERVICEACCOUNT_CA_PATH", "/var/run/secrets/kubernetes.io/serviceaccount/ca.crt")
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request = Request(
        f"{base_url}{path}",
        method=method,
        data=data,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": content_type,
        },
    )
    try:
        import ssl

        context = ssl.create_default_context(cafile=ca_file if Path(ca_file).exists() else None)
        with urlopen(request, timeout=5, context=context) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise KubernetesRuntimeError(f"Kubernetes API returned {exc.code}: {detail or exc.reason}") from exc
    except (URLError, TimeoutError, OSError, ValueError) as exc:
        raise KubernetesRuntimeError(f"Kubernetes API request failed: {exc}") from exc


def _service_account_token() -> str:
    token_path = Path(os.getenv("KUBERNETES_SERVICEACCOUNT_TOKEN_PATH", "/var/run/secrets/kubernetes.io/serviceaccount/token"))
    if not token_path.exists():
        return ""
    try:
        return token_path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def _require_service_account_token() -> str:
    token = _service_account_token()
    if not token:
        raise KubernetesRuntimeError("Kubernetes service account token is not available.")
    return token


def _business_key_from_namespace(namespace: str) -> str:
    match = re.match(r"^[a-z0-9-]+-biz-([a-z0-9-]+?)(?:-[0-9]+x[0-9]+)?$", namespace)
    if match:
        return match.group(1)
    if "-business-" not in namespace:
        return ""
    return namespace.rsplit("-business-", 1)[-1]


def _dns_label(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9-]+", "-", value.strip().lower()).strip("-")
    normalized = re.sub(r"-+", "-", normalized)
    if not normalized:
        raise KubernetesRuntimeError("Namespace key cannot be empty.")
    if len(normalized) > 63:
        raise KubernetesRuntimeError(f"Namespace key {value!r} is too long.")
    return normalized
