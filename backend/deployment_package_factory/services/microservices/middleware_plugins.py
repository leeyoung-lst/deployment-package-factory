from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MiddlewarePlugin:
    key: str
    name: str
    env_name: str
    default_endpoint: str
    description: str

    def env_line(self) -> str:
        return f"{self.env_name}={self.default_endpoint}"

    def placeholder_line(self) -> str:
        return f"{self.env_name}=__REPLACE_WITH_{self.env_name}__"

    def yaml_block(self) -> str:
        return f"  {self.key}:\n    endpoint: ${{{self.env_name}}}\n    description: {self.description}"

    def ts_entry(self) -> str:
        return f"{self.key}: process.env.{self.env_name} || ''"


MIDDLEWARE_PLUGINS: dict[str, MiddlewarePlugin] = {
    "redis": MiddlewarePlugin("redis", "Redis", "REDIS_ENDPOINT", "redis://redis:6379/0", "cache and distributed lock"),
    "dm": MiddlewarePlugin("dm", "达梦 DM", "DM_ENDPOINT", "dm://dm:5236/APP", "domestic relational database"),
    "postgresql": MiddlewarePlugin("postgresql", "PostgreSQL", "POSTGRESQL_ENDPOINT", "postgresql://app:__REPLACE_WITH_POSTGRES_PASSWORD__@postgresql:5432/app", "relational database"),
    "iotdb": MiddlewarePlugin("iotdb", "IoTDB", "IOTDB_ENDPOINT", "iotdb://iotdb:6667", "time-series storage"),
    "mongodb": MiddlewarePlugin("mongodb", "MongoDB", "MONGODB_ENDPOINT", "mongodb://mongodb:27017/app", "document database"),
    "kafka": MiddlewarePlugin("kafka", "Kafka", "KAFKA_ENDPOINT", "kafka:9092", "event streaming"),
    "mq": MiddlewarePlugin("mq", "消息队列 MQ", "MQ_ENDPOINT", "mq:5672", "message queue"),
    "nacos": MiddlewarePlugin("nacos", "Nacos", "NACOS_ENDPOINT", "nacos:8848", "service discovery and configuration"),
}


def middleware_catalog() -> dict[str, str]:
    return {key: plugin.name for key, plugin in MIDDLEWARE_PLUGINS.items()}


def selected_plugins(keys: list[str]) -> list[MiddlewarePlugin]:
    return [MIDDLEWARE_PLUGINS[key] for key in keys if key in MIDDLEWARE_PLUGINS]


def env_placeholder_lines(keys: list[str]) -> list[str]:
    return [plugin.placeholder_line() for plugin in selected_plugins(keys)]


def env_default_lines(keys: list[str]) -> list[str]:
    return [plugin.env_line() for plugin in selected_plugins(keys)]


def middleware_yaml(keys: list[str]) -> str:
    lines = ["middleware:"]
    lines.extend(plugin.yaml_block() for plugin in selected_plugins(keys))
    return "\n".join(lines) + "\n"


def middleware_ts(keys: list[str]) -> str:
    entries = ", ".join(plugin.ts_entry() for plugin in selected_plugins(keys))
    return f"export const middleware = {{ {entries} }};\n"


def required_env_names(keys: list[str]) -> list[str]:
    return [plugin.env_name for plugin in selected_plugins(keys)]
