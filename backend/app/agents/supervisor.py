"""
Supervisor agent: decides which specialist agents need to run for this
incident. Uses non_think mode — this is a routing decision, not deep
reasoning, so latency matters more than depth here.
"""

import json
import logging

from app.agents.prompts import SUPERVISOR_SYSTEM_PROMPT
from app.agents.state import OpsAgentState
from app.db.redis_client import publish_event
from app.llm.deepseek_client import chat_completion, estimate_cost_usd

logger = logging.getLogger("opsagent.agents.supervisor")


def supervisor_node(state: OpsAgentState) -> dict:
    alert = state["raw_alert"]
    retry_count = state.get("retry_count", 0)

    retry_note = ""
    if retry_count > 0:
        retry_note = (
            f"\nThis is retry #{retry_count} after a failed verification. "
            f"Verification output: {state.get('verification_output', '')[:500]}"
        )

    messages = [
        {"role": "system", "content": SUPERVISOR_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"Incident alert payload:\n{json.dumps(alert)[:4000]}{retry_note}\n\n"
                'Respond ONLY with JSON in this exact shape: '
                '{"needs_log_analysis": bool, "needs_security_scan": bool, "reasoning": str}'
            ),
        },
    ]
    message, usage, _ = chat_completion(messages, mode="non_think", temperature=0.0)

    try:
        decision = json.loads(message.content)
    except (json.JSONDecodeError, TypeError):
        logger.warning("Supervisor returned malformed JSON, falling back to running both agents")
        decision = {
            "needs_log_analysis": True,
            "needs_security_scan": True,
            "reasoning": "fallback: malformed routing response, running all checks",
        }

    cost = estimate_cost_usd(usage, "non_think")
    publish_event(
        state["incident_id"],
        {"agent": "supervisor", "event": "routing_decision", "detail": decision, "cost_usd": cost},
    )

    token_usage = dict(state.get("token_usage", {}))
    token_usage["supervisor"] = token_usage.get("supervisor", 0) + usage.get("total_tokens", 0)

    return {
        "needs_log_analysis": bool(decision.get("needs_log_analysis", True)),
        "needs_security_scan": bool(decision.get("needs_security_scan", True)),
        "status": "routing",
        "token_usage": token_usage,
        "messages": [{"role": "assistant", "content": f"[supervisor] {decision.get('reasoning', '')}"}],
    }
