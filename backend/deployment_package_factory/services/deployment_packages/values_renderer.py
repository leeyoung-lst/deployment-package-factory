from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import PurePosixPath


@dataclass(frozen=True)
class RenderedValuesFile:
    path: PurePosixPath
    content: str
    executable: bool = False


def render_values_files(manifest: dict) -> list[RenderedValuesFile]:
    values = {
        "schemaVersion": "deployment-values/v1",
        "packageId": manifest["packageId"],
        "projectKey": manifest.get("projectKey") or "custom",
        "productVersion": manifest.get("productVersion") or "",
        "sourceEnv": manifest.get("sourceEnv") or "",
        "targetEnv": manifest.get("targetEnv") or "",
        "deployModes": manifest.get("deployModes") or [],
        "imageMode": manifest.get("imageMode") or "image-manifest",
        "targetProfile": manifest.get("targetProfile") or {},
        "namespaces": _namespaces(manifest),
        "k8s": {
            "layers": _k8s_layers(manifest),
        },
        "database": {
            "key": manifest.get("database") or "",
            "image": manifest.get("databaseImage") or "",
        },
        "services": _services(manifest),
        "middleware": _middleware(manifest),
        "images": _images(manifest),
        "validationSummary": manifest.get("validationSummary") or {},
        "initialization": {
            "root": "init/",
            "projectOverlay": f"init/project/{manifest.get('projectKey')}" if manifest.get("projectKey") else "",
        },
    }
    return [
        RenderedValuesFile(PurePosixPath("deploy-values.json"), json.dumps(values, ensure_ascii=False, indent=2) + "\n"),
    ]


def _namespaces(manifest: dict) -> dict:
    prefix = (manifest.get("targetProfile") or {}).get("namespacePrefix") or "prod"
    return {
        "basePublic": f"{prefix}-base-public",
        "middleware": f"{prefix}-middleware",
        "business": {
            key: f"{prefix}-business-{key}"
            for key in manifest.get("businessServices", [])
        },
    }


def _services(manifest: dict) -> list[dict]:
    namespaces = _namespaces(manifest)
    return [
        {
            "key": key,
            "group": "platform",
            "namespace": namespaces["basePublic"],
        }
        for key in manifest.get("platformServices", [])
    ] + [
        {
            "key": key,
            "group": "business",
            "namespace": namespaces["business"].get(key, namespaces["basePublic"]),
        }
        for key in manifest.get("businessServices", [])
    ]


def _middleware(manifest: dict) -> list[dict]:
    namespace = _namespaces(manifest)["middleware"]
    return [
        {
            "key": key,
            "namespace": namespace,
            "required": key == manifest.get("database"),
        }
        for key in manifest.get("middleware", [])
    ]


def _k8s_layers(manifest: dict) -> list[dict]:
    layer_specs = [
        ("00-platform", "local-ai-platform", ["namespaces", "configmaps", "secrets"]),
        ("10-data", "local-ai-data", [key for key in _runtime_middleware_keys(manifest) if _k8s_layer_for_middleware(key) == "10-data"]),
        ("20-observability", "local-ai-observability", [key for key in _runtime_middleware_keys(manifest) if _k8s_layer_for_middleware(key) == "20-observability"]),
        ("30-edge", "local-ai-edge", [key for key in _runtime_middleware_keys(manifest) if _k8s_layer_for_middleware(key) == "30-edge"]),
        ("40-workflow-webui", "local-ai-workflow-webui", [key for key in _runtime_middleware_keys(manifest) if _k8s_layer_for_middleware(key) == "40-workflow-webui"]),
        ("50-simulators", "local-ai-simulators-ha", []),
        ("60-apps", "local-ai-apps", [*manifest.get("platformServices", []), *manifest.get("businessServices", [])]),
    ]
    return [
        {
            "name": name,
            "release": release,
            "enabled": bool(components),
            "components": components,
        }
        for name, release, components in layer_specs
    ]


def _runtime_middleware_keys(manifest: dict) -> list[str]:
    keys = [manifest.get("database") or "", *manifest.get("middleware", [])]
    return [key for key in dict.fromkeys(keys) if key]


def _k8s_layer_for_middleware(key: str) -> str:
    if key in {"iotdb", "mqtt", "mqtt-broker", "mqtt-collector", "collection-metrics"}:
        return "30-edge"
    if key in {"camunda", "camunda-elasticsearch", "open-webui"}:
        return "40-workflow-webui"
    if key in {"monitoring", "prometheus", "grafana", "alertmanager"}:
        return "20-observability"
    return "10-data"


def _images(manifest: dict) -> list[dict]:
    return [
        {
            "group": item.get("group") or "",
            "sourceRef": item.get("sourceRef") or "",
            "targetRef": item.get("targetRef") or "",
            "archiveFile": item.get("archiveFile") or "",
        }
        for item in manifest.get("imageEntries", [])
    ]
