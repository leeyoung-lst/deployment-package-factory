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


def not_ready_microservice_details(services: list[dict]) -> list[dict[str, object]]:
    return [
        {
            "projectId": service.get("projectId") or "",
            "serviceKey": service.get("serviceKey") or "",
            "serviceName": service.get("serviceName") or service.get("serviceKey") or "",
            "status": (service.get("delivery") or {}).get("status") or "unknown",
            "buildStatus": ((service.get("delivery") or {}).get("build") or {}).get("status") or "unknown",
            "jenkinsUrl": ((service.get("delivery") or {}).get("build") or {}).get("url") or "",
        }
        for service in services
        if not microservice_delivery_succeeded(service)
    ]


def microservice_delivery_not_ready_error(services: list[dict]) -> dict[str, object]:
    details = not_ready_microservice_details(services)
    names = "、".join(str(item["serviceName"]) for item in details)
    return {
        "code": "MICROSERVICE_DELIVERY_NOT_READY",
        "message": f"以下注册微服务尚未构建成功：{names}",
        "services": details,
    }
