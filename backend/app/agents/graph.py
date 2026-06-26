"""
Builds and compiles the OpsAgent-X state graph:

    START -> supervisor -> {log_analyst, security_agent} (parallel fan-out)
                              \\            /
                               -> code_fixer (fan-in: waits for both)
                                     -> verification
                                          -> [fail, retries left]  -> supervisor
                                          -> [fail, retries exhausted] -> human_approval
                                          -> [pass] -> human_approval
                                               -> [approved] -> deploy -> END
                                               -> [rejected] -> END

State is checkpointed to Redis via RedisSaver, so a pod crash mid-incident
resumes exactly where it left off — including while paused at the
human-in-the-loop interrupt.
"""

import logging

from langgraph.checkpoint.redis import RedisSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from app.agents.code_fixer import code_fixer_node
from app.agents.log_analyst import log_analyst_node
from app.agents.security_agent import security_agent_node
from app.agents.state import OpsAgentState
from app.agents.supervisor import supervisor_node
from app.agents.verification import verification_node
from app.config import settings
from app.db.redis_client import publish_event

logger = logging.getLogger("opsagent.agents.graph")


def human_approval_node(state: OpsAgentState) -> dict:
    """Pauses the graph and waits for a human to approve/reject via the dashboard."""
    publish_event(state["incident_id"], {"agent": "human_in_the_loop", "event": "awaiting_approval"})

    if not settings.REQUIRE_HUMAN_APPROVAL:
        return {"human_decision": True, "status": "auto_approved"}

    decision = interrupt(
        {
            "incident_id": state["incident_id"],
            "branch_name": state.get("branch_name"),
            "patch_summary": state.get("patch_diff"),
            "verification_passed": state.get("verification_passed"),
            "question": "Approve this patch for deployment?",
        }
    )
    return {"human_decision": bool(decision.get("approved", False)), "status": "human_reviewed"}


def deploy_node(state: OpsAgentState) -> dict:
    """Hands the approved branch off for rollout.

    Stubbed intentionally: wire this to your real ArgoCD Application sync
    (or a `kubectl apply` against a reviewed manifest) once you've watched
    the patch flow end-to-end in staging. Nothing in this codebase should
    auto-deploy to production without that explicit integration."""
    publish_event(state["incident_id"], {"agent": "deploy", "event": "deploy_requested", "branch": state.get("branch_name")})
    return {"status": "deployed"}


def route_after_supervisor(state: OpsAgentState) -> list[str]:
    targets = []
    if state.get("needs_log_analysis", True):
        targets.append("log_analyst")
    if state.get("needs_security_scan", True):
        targets.append("security_agent")
    return targets or ["log_analyst"]


def route_after_verification(state: OpsAgentState) -> str:
    if state.get("verification_passed"):
        return "human_approval"
    if state.get("retry_count", 0) >= settings.MAX_RETRIES:
        publish_event(state["incident_id"], {"agent": "graph", "event": "max_retries_exhausted"})
        return "human_approval"
    return "supervisor"


def route_after_approval(state: OpsAgentState) -> str:
    return "deploy" if state.get("human_decision") else END


def build_graph() -> StateGraph:
    graph = StateGraph(OpsAgentState)

    graph.add_node("supervisor", supervisor_node)
    graph.add_node("log_analyst", log_analyst_node)
    graph.add_node("security_agent", security_agent_node)
    graph.add_node("code_fixer", code_fixer_node)
    graph.add_node("verification", verification_node)
    graph.add_node("human_approval", human_approval_node)
    graph.add_node("deploy", deploy_node)

    graph.add_edge(START, "supervisor")
    graph.add_conditional_edges("supervisor", route_after_supervisor, ["log_analyst", "security_agent"])
    graph.add_edge("log_analyst", "code_fixer")
    graph.add_edge("security_agent", "code_fixer")
    graph.add_edge("code_fixer", "verification")
    graph.add_conditional_edges("verification", route_after_verification, ["supervisor", "human_approval"])
    graph.add_conditional_edges("human_approval", route_after_approval, ["deploy", END])
    graph.add_edge("deploy", END)

    return graph


# --- Checkpointer + compiled graph lifecycle -------------------------------
# RedisSaver is a context manager. We enter it once at app startup and exit
# it at shutdown (see main.py's lifespan handler), rather than per-request.

_checkpointer_cm = None
_checkpointer = None
_compiled_graph = None


def init_graph():
    global _checkpointer_cm, _checkpointer, _compiled_graph
    if _compiled_graph is not None:
        return _compiled_graph

    _checkpointer_cm = RedisSaver.from_conn_string(settings.REDIS_URL)
    _checkpointer = _checkpointer_cm.__enter__()
    _checkpointer.setup()  # creates Redis indices on first run; safe to call every boot
    _compiled_graph = build_graph().compile(checkpointer=_checkpointer)
    logger.info("LangGraph compiled with RedisSaver checkpointer at %s", settings.REDIS_URL)
    return _compiled_graph


def get_compiled_graph():
    return _compiled_graph if _compiled_graph is not None else init_graph()


def shutdown_graph() -> None:
    global _checkpointer_cm
    if _checkpointer_cm is not None:
        _checkpointer_cm.__exit__(None, None, None)
        _checkpointer_cm = None
