"""
LogAnalyst agent: investigates the incident using K8s logs + PromQL, then
produces a root-cause diagnosis. Uses think_high mode — this needs real
reasoning across multiple log lines and metrics, but doesn't need the
full cost of think_max (that's reserved for CodeFixer).
"""

import logging

from app.agents.prompts import LOG_ANALYST_SYSTEM_PROMPT
from app.agents.state import OpsAgentState
from app.db.redis_client import publish_event
from app.llm.deepseek_client import estimate_cost_usd, run_tool_agent
from app.tools.k8s_tools import k8s_fetch_logs, promql_query

logger = logging.getLogger("opsagent.agents.log_analyst")

TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "k8s_fetch_logs",
            "description": "Fetch recent logs for a pod/container in an allow-listed namespace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "namespace": {"type": "string"},
                    "pod_name": {"type": "string"},
                    "container": {"type": "string"},
                    "tail_lines": {"type": "integer", "default": 200},
                },
                "required": ["namespace", "pod_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "promql_query",
            "description": "Run an instant PromQL query against the cluster's Prometheus.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
    },
]


def _execute_tool(name: str, args: dict) -> str:
    if name == "k8s_fetch_logs":
        return k8s_fetch_logs(**args)
    if name == "promql_query":
        return promql_query(**args)
    return f"ERROR: unknown tool '{name}'"


def log_analyst_node(state: OpsAgentState) -> dict:
    if not state.get("needs_log_analysis", True):
        return {"diagnosis": "Skipped by supervisor — alert did not require log analysis."}

    publish_event(state["incident_id"], {"agent": "log_analyst", "event": "started"})

    user_prompt = (
        f"Incident alert:\n{state['raw_alert']}\n\n"
        "Investigate using the available tools, then respond with a concise root-cause "
        "diagnosis and which file/service is most likely responsible."
    )
    diagnosis, usage, _ = run_tool_agent(
        LOG_ANALYST_SYSTEM_PROMPT, user_prompt, TOOLS_SCHEMA, _execute_tool, mode="think_high"
    )

    cost = estimate_cost_usd(usage, "think_high")
    publish_event(state["incident_id"], {"agent": "log_analyst", "event": "completed", "cost_usd": cost})

    token_usage = dict(state.get("token_usage", {}))
    token_usage["log_analyst"] = token_usage.get("log_analyst", 0) + usage.get("total_tokens", 0)

    return {
        "diagnosis": diagnosis,
        "status": "diagnosing",
        "token_usage": token_usage,
        "messages": [{"role": "assistant", "content": f"[log_analyst] {diagnosis}"}],
    }
