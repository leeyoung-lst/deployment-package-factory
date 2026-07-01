from __future__ import annotations

from urllib.parse import quote

from deployment_package_factory.services.microservices.middleware_plugins import MIDDLEWARE_PLUGINS

DEFAULT_PORTS = {
    "redis": 6379,
    "postgresql": 5432,
    "dm": 5236,
    "iotdb": 6667,
    "mongodb": 27017,
    "kafka": 9092,
    "mq": 5672,
    "nacos": 8848,
}
DEFAULT_HOSTS = {"postgresql": "postgres"}
DEFAULT_DATABASES = {"redis": "0", "postgresql": "app", "mongodb": "app"}
DEFAULT_USERS = {"postgresql": "app"}


def middleware_config_keys(tech_stack: str, middleware: list[str]) -> list[str]:
    keys = list(dict.fromkeys(middleware))
    if tech_stack == "java-spring-cloud-alibaba" and "nacos" not in keys:
        keys.append("nacos")
    return keys


def build_middleware_config(keys: list[str], source_env: str, settings_middleware: object | None) -> dict[str, dict[str, object]]:
    return {
        key: normalize_middleware_config(key, _endpoint_settings(settings_middleware, key), source_env)
        for key in middleware_config_keys("", keys)
        if key in MIDDLEWARE_PLUGINS
    }


def resolve_middleware_config(keys: list[str], provided: dict[str, object], source_env: str) -> dict[str, dict[str, object]]:
    return {
        key: normalize_middleware_config(key, provided.get(key) if isinstance(provided, dict) else None, source_env)
        for key in keys
        if key in MIDDLEWARE_PLUGINS
    }


def env_lines(keys: list[str], configs: dict[str, dict[str, object]]) -> list[str]:
    lines: list[str] = []
    for key in keys:
        plugin = MIDDLEWARE_PLUGINS.get(key)
        if plugin is None:
            continue
        lines.append(f"{plugin.env_name}={endpoint_for(key, configs.get(key, {}))}")
    return lines


def plugin_runtime_env(keys: list[str], configs: dict[str, dict[str, object]]) -> dict[str, dict[str, object]]:
    env: dict[str, dict[str, object]] = {}
    for key in keys:
        plugin = MIDDLEWARE_PLUGINS.get(key)
        if plugin is None:
            continue
        config = configs.get(key, {})
        value = endpoint_for(key, config)
        env[plugin.env_name] = {"value": value, "secret": _contains_password(config, value)}
    return env


def python_runtime_env(keys: list[str], configs: dict[str, dict[str, object]]) -> dict[str, dict[str, object]]:
    env: dict[str, dict[str, object]] = {}
    if "redis" in keys:
        redis_config = configs.get("redis", {})
        env["REDIS_URL"] = {"value": redis_url(redis_config), "secret": bool(_text(redis_config, "password"))}
    if "postgresql" in keys:
        env["POSTGRES_DSN"] = {"value": postgres_dsn(configs.get("postgresql", {})), "secret": True}
    env.update(plugin_runtime_env([key for key in keys if key not in {"redis", "postgresql"}], configs))
    return env


def endpoint_for(key: str, config: dict[str, object]) -> str:
    explicit = _text(config, "endpoint")
    if explicit:
        return explicit
    if key == "redis":
        return redis_url(config)
    if key == "postgresql":
        return postgres_dsn(config)
    host = _qualified_host(config)
    port = int(config.get("port") or DEFAULT_PORTS.get(key) or 0)
    database = _text(config, "database")
    username = _text(config, "username")
    password = _text(config, "password")
    if key == "mongodb":
        auth = _auth_prefix(username, password)
        return f"mongodb://{auth}{host}:{port}/{database or 'app'}"
    if key == "dm":
        auth = _auth_prefix(username, password)
        path = f"/{database}" if database else ""
        return f"dm://{auth}{host}:{port}{path}"
    if key == "iotdb":
        auth = _auth_prefix(username, password)
        return f"iotdb://{auth}{host}:{port}"
    return f"{host}:{port}" if port else host


def redis_url(config: dict[str, object]) -> str:
    explicit = _text(config, "endpoint")
    if explicit.startswith("redis://"):
        return explicit
    host = _qualified_host(config)
    port = int(config.get("port") or DEFAULT_PORTS["redis"])
    database = _text(config, "database") or "0"
    username = _text(config, "username")
    password = _text(config, "password")
    return f"redis://{_auth_prefix(username, password)}{host}:{port}/{database}"


def postgres_dsn(config: dict[str, object]) -> str:
    explicit = _text(config, "endpoint")
    if explicit.startswith(("postgresql://", "postgres://")):
        return explicit
    host = _qualified_host(config)
    port = int(config.get("port") or DEFAULT_PORTS["postgresql"])
    username = _text(config, "username") or DEFAULT_USERS["postgresql"]
    password = _text(config, "password") or "__REPLACE_WITH_POSTGRES_PASSWORD__"
    database = _text(config, "database") or DEFAULT_DATABASES["postgresql"]
    return f"postgresql://{quote(username, safe='')}:{quote(password, safe='')}@{host}:{port}/{database}"


def normalize_middleware_config(key: str, raw: object, source_env: str) -> dict[str, object]:
    namespace = _raw_text(raw, "namespace") or f"{source_env}-middleware-public"
    host = _raw_text(raw, "host") or DEFAULT_HOSTS.get(key, key)
    config = {
        "enabled": _raw_bool(raw, "enabled", True),
        "host": host,
        "port": _raw_port(raw, "port") or DEFAULT_PORTS.get(key),
        "username": _raw_text(raw, "username") or DEFAULT_USERS.get(key, ""),
        "password": _raw_text(raw, "password"),
        "database": _raw_text(raw, "database") or DEFAULT_DATABASES.get(key, ""),
        "namespace": namespace,
        "endpoint": _raw_text(raw, "endpoint"),
    }
    config["qualifiedHost"] = _qualified_host(config)
    config["resolvedEndpoint"] = endpoint_for(key, config)
    return config


def _endpoint_settings(settings_middleware: object | None, key: str) -> object | None:
    return getattr(settings_middleware, key, None) if settings_middleware is not None else None


def _qualified_host(config: dict[str, object]) -> str:
    host = _text(config, "host")
    namespace = _text(config, "namespace")
    if "://" in host or not namespace or _looks_external(host):
        return host
    return f"{host}.{namespace}.svc.cluster.local"


def _looks_external(host: str) -> bool:
    return "." in host or ":" in host or host in {"localhost", "127.0.0.1", "::1"}


def _auth_prefix(username: str, password: str) -> str:
    if not password and not username:
        return ""
    if username:
        return f"{quote(username, safe='')}:{quote(password, safe='')}@"
    return f":{quote(password, safe='')}@"


def _contains_password(config: dict[str, object], value: str) -> bool:
    password = _text(config, "password")
    return bool(password and password in value)


def _raw_text(raw: object, field: str) -> str:
    if raw is None:
        return ""
    if isinstance(raw, dict):
        return str(raw.get(field) or "").strip()
    return str(getattr(raw, field, "") or "").strip()


def _text(config: dict[str, object], field: str) -> str:
    return str(config.get(field) or "").strip()


def _raw_bool(raw: object, field: str, default: bool) -> bool:
    if raw is None:
        return default
    value = raw.get(field) if isinstance(raw, dict) else getattr(raw, field, default)
    return bool(value)


def _raw_port(raw: object, field: str) -> int | None:
    if raw is None:
        return None
    value = raw.get(field) if isinstance(raw, dict) else getattr(raw, field, None)
    try:
        port = int(value)
    except (TypeError, ValueError):
        return None
    return port if 1 <= port <= 65535 else None
