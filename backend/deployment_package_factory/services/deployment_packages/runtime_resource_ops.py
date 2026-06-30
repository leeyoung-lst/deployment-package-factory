from __future__ import annotations

import re

from deployment_package_factory.services.deployment_packages.runtime_env_values import is_resolved_value


def dedupe_resources(resources: list[dict]) -> list[dict]:
    result: dict[str, dict] = {}
    for resource in resources:
        key = resource["key"]
        if key not in result:
            result[key] = resource
            continue
        existing = result[key]
        existing["usedBy"] = list(dict.fromkeys([*existing.get("usedBy", []), *resource.get("usedBy", [])]))
        existing["shared"] = len(existing["usedBy"]) > 1
        existing["needsReview"] = bool(existing.get("needsReview")) and bool(resource.get("needsReview"))
        if existing.get("source") != "pod-env" and resource.get("source") == "pod-env":
            existing["source"] = "pod-env"
            existing["items"] = resource.get("items", existing.get("items", []))
    return sorted(result.values(), key=lambda item: (item["type"], item["key"]))


def apply_resource_overrides(resource: dict, overrides: dict[str, str]) -> dict:
    resource = {**resource}
    updated_items = []
    for item in resource.get("items", []):
        override_name = _resource_override_name(resource["key"], item)
        value = item.get("value", "") if item.get("editable") is False else overrides.get(override_name, item.get("value", ""))
        updated_items.append({**item, "overrideName": override_name, "value": value, "resolved": is_resolved_value(value)})
    resource["items"] = updated_items
    if resource.get("type") == "databaseSchema":
        _apply_database_name(resource, updated_items)
    elif resource.get("type") in {"bucket", "collection"}:
        _apply_named_resource(resource, updated_items)
    return resource


def resource_key(*parts: str) -> str:
    return "-".join(re.sub(r"[^a-z0-9]+", "-", str(part).lower()).strip("-") for part in parts if str(part))


def _apply_database_name(resource: dict, items: list[dict]) -> None:
    database_name = _item_value(items, "databaseName")
    schema = _item_value(items, "schema")
    if database_name and schema:
        resource["name"] = f"{resource.get('middlewareKey')} {database_name}.{schema}"
        resource["key"] = resource_key("databaseSchema", resource.get("middlewareKey", ""), database_name, schema)


def _apply_named_resource(resource: dict, items: list[dict]) -> None:
    name = _item_value(items, "bucket") or _item_value(items, "collection") or resource.get("name", "")
    resource["name"] = name
    resource["key"] = resource_key(str(resource.get("type")), resource.get("middlewareKey", ""), name)


def _resource_override_name(resource_key_value: str, item: dict) -> str:
    name = str(item.get("name") or "")
    return f"{resource_key_value}.{name}"


def _item_value(items: list[dict], name: str) -> str:
    for item in items:
        if item.get("name") == name:
            return str(item.get("value") or "")
    return ""
