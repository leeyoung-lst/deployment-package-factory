from __future__ import annotations


def microservice_delivery_succeeded(service: dict) -> bool:
    delivery = service.get("delivery") or {}
    build = delivery.get("build") or {}
    return delivery.get("status") == "success" or build.get("status") == "success"


def microservice_delivery_warning(service: dict) -> str:
    return (
        f"微服务 {service.get('serviceKey') or service.get('serviceName')} 构建状态为 "
        f"{microservice_delivery_status(service)}，导包前建议先完成流水线验证。"
    )


def microservice_delivery_status(service: dict) -> str:
    delivery = service.get("delivery") or {}
    build = delivery.get("build") or {}
    return str(build.get("status") or delivery.get("status") or "unknown")


def not_ready_microservices(services: list[dict]) -> list[str]:
    return [
        f"{service.get('serviceKey')}({microservice_delivery_status(service)})"
        for service in services
        if not microservice_delivery_succeeded(service)
    ]
