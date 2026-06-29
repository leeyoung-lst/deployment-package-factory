from __future__ import annotations


def render_metrics(task_repo, audit_repo) -> str:
    task_summary = task_repo.metrics_summary()
    audit_summary = audit_repo.metrics_summary()
    lines = [
        "# HELP deployment_package_tasks_total Total deployment package tasks.",
        "# TYPE deployment_package_tasks_total counter",
        f"deployment_package_tasks_total {int(task_summary['total'])}",
        "# HELP deployment_package_tasks_by_status Deployment package tasks grouped by status.",
        "# TYPE deployment_package_tasks_by_status gauge",
    ]
    for status, count in sorted(task_summary["byStatus"].items()):
        lines.append(f'deployment_package_tasks_by_status{{status="{_label(status)}"}} {int(count)}')
    lines.extend(
        [
            "# HELP deployment_package_artifacts_available Available completed package artifacts.",
            "# TYPE deployment_package_artifacts_available gauge",
            f"deployment_package_artifacts_available {int(task_summary['availableArtifacts'])}",
            "# HELP deployment_package_artifacts_bytes Total bytes of available package artifacts.",
            "# TYPE deployment_package_artifacts_bytes gauge",
            f"deployment_package_artifacts_bytes {int(task_summary['artifactBytes'])}",
            "# HELP deployment_package_audit_events_total Total deployment package audit events.",
            "# TYPE deployment_package_audit_events_total counter",
            f"deployment_package_audit_events_total {int(audit_summary['total'])}",
            "# HELP deployment_package_audit_events_by_action Deployment package audit events grouped by action.",
            "# TYPE deployment_package_audit_events_by_action gauge",
        ]
    )
    for action, count in sorted(audit_summary["byAction"].items()):
        lines.append(f'deployment_package_audit_events_by_action{{action="{_label(action)}"}} {int(count)}')
    return "\n".join(lines) + "\n"


def _label(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
