"""
Read-only Kubernetes + Prometheus tools for the LogAnalyst agent.

Safety constraint: K8s_Fetch_Logs refuses to read from any namespace not
explicitly listed in settings.ALLOWED_NAMESPACES, regardless of what the
model asks for. There is intentionally no write/delete/exec tool here —
this agent only ever reads.
"""

import logging

import requests
from kubernetes import client, config as k8s_config

from app.config import settings

logger = logging.getLogger("opsagent.tools.k8s")

_loaded = False


def _ensure_loaded() -> None:
    global _loaded
    if _loaded:
        return
    if settings.K8S_IN_CLUSTER:
        k8s_config.load_incluster_config()
    else:
        k8s_config.load_kube_config(config_file=settings.K8S_KUBECONFIG)
    _loaded = True


def k8s_fetch_logs(namespace: str, pod_name: str, container: str | None = None, tail_lines: int = 200) -> str:
    """Tool: fetch recent logs for a pod/container. Namespace must be allow-listed."""
    if namespace not in settings.ALLOWED_NAMESPACES:
        return f"DENIED: namespace '{namespace}' is not in ALLOWED_NAMESPACES {settings.ALLOWED_NAMESPACES}."

    try:
        _ensure_loaded()
        v1 = client.CoreV1Api()
        return v1.read_namespaced_pod_log(
            name=pod_name, namespace=namespace, container=container, tail_lines=tail_lines
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("k8s_fetch_logs failed")
        return f"ERROR fetching logs: {exc}"


def promql_query(query: str) -> str:
    """Tool: run an instant PromQL query against the cluster's Prometheus."""
    try:
        resp = requests.get(f"{settings.PROMETHEUS_URL}/api/v1/query", params={"query": query}, timeout=10)
        resp.raise_for_status()
        return resp.text
    except Exception as exc:  # noqa: BLE001
        logger.exception("promql_query failed")
        return f"ERROR running PromQL query: {exc}"
