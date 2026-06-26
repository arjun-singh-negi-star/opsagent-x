"""
Shared state that flows through every node in the OpsAgent-X graph.

This is a TypedDict (LangGraph's preferred state shape) rather than a
Pydantic model, since LangGraph merges partial dict returns from each node
into this state automatically.
"""

from typing import Annotated, TypedDict

from langgraph.graph.message import add_messages


class OpsAgentState(TypedDict, total=False):
    incident_id: str
    raw_alert: dict

    # Supervisor's routing decision
    needs_log_analysis: bool
    needs_security_scan: bool

    # LogAnalyst / SecurityAgent output
    diagnosis: str
    security_findings: str

    # CodeFixer output
    patch_diff: str
    branch_name: str

    # Verification output
    verification_passed: bool
    verification_output: str
    retry_count: int

    # Human-in-the-loop
    human_decision: bool

    # Bookkeeping
    status: str
    token_usage: dict[str, int]
    messages: Annotated[list, add_messages]
