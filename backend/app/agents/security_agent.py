"""
SecurityAgent: runs a Trivy scan against the implicated image. Uses
non_think mode per the spec — this is a quick triage pass, and detailed
reasoning about exploitability is left to a human if anything serious
turns up.
"""

import logging

from app.agents.prompts import SECURITY_AGENT_SYSTEM_PROMPT
from app.agents.state import OpsAgentState
from app.db.redis_client import publish_event
from app.llm.deepseek_client import estimate_cost_usd, run_tool_agent
from app.tools.security_tools import trivy_scan

logger = logging.getLogger("opsagent.agents.security")

TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "trivy_scan",
            "description": "Run a Trivy CRITICAL/HIGH vulnerability scan against a container image.",
            "parameters": {
                "type": "object",
                "properties": {"image": {"type": "string"}},
                "required": ["image"],
            },
        },
    }
]


def _execute_tool(name: str, args: dict) -> str:
    if name == "trivy_scan":
        return trivy_scan(**args)
    return f"ERROR: unknown tool '{name}'"


def security_agent_node(state: OpsAgentState) -> dict:
    if not state.get("needs_security_scan", True):
        return {"security_findings": "Skipped by supervisor — alert did not indicate a security risk."}

    publish_event(state["incident_id"], {"agent": "security_agent", "event": "started"})

    image = state["raw_alert"].get("image") or state["raw_alert"].get("service", "unknown:latest")
    user_prompt = f"Scan the image/service implicated in this incident: {image}. Summarize any CRITICAL/HIGH findings."
    findings, usage, _ = run_tool_agent(
        SECURITY_AGENT_SYSTEM_PROMPT, user_prompt, TOOLS_SCHEMA, _execute_tool, mode="non_think"
    )

    cost = estimate_cost_usd(usage, "non_think")
    publish_event(state["incident_id"], {"agent": "security_agent", "event": "completed", "cost_usd": cost})

    token_usage = dict(state.get("token_usage", {}))
    token_usage["security_agent"] = token_usage.get("security_agent", 0) + usage.get("total_tokens", 0)

    return {
        "security_findings": findings,
        "token_usage": token_usage,
        "messages": [{"role": "assistant", "content": f"[security_agent] {findings}"}],
    }
