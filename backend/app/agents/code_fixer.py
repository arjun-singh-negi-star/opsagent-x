"""
CodeFixer agent: writes and applies the patch. Uses think_max — the
highest reasoning effort DeepSeek-V4 Flash supports — since a wrong fix
here is the most expensive mistake in the whole pipeline.

It only ever commits to a local feature branch (see tools/git_tools.py).
Nothing here pushes, merges, or deploys.
"""

import logging
import uuid

from app.agents.prompts import CODE_FIXER_SYSTEM_PROMPT
from app.agents.state import OpsAgentState
from app.db.redis_client import publish_event
from app.llm.deepseek_client import estimate_cost_usd, run_tool_agent
from app.tools.git_tools import code_patch, git_create_branch

logger = logging.getLogger("opsagent.agents.code_fixer")

TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "git_create_branch",
            "description": "Create a feature branch off origin/main for this incident's fix.",
            "parameters": {
                "type": "object",
                "properties": {"branch_name": {"type": "string"}},
                "required": ["branch_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "code_patch",
            "description": (
                "Apply a unified diff to ONE file inside the repo and commit it to the "
                "current branch. Never pushes or merges."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string"},
                    "unified_diff": {"type": "string"},
                },
                "required": ["file_path", "unified_diff"],
            },
        },
    },
]


def _execute_tool(name: str, args: dict) -> str:
    if name == "git_create_branch":
        return git_create_branch(**args)
    if name == "code_patch":
        return code_patch(**args)
    return f"ERROR: unknown tool '{name}'"


def code_fixer_node(state: OpsAgentState) -> dict:
    publish_event(state["incident_id"], {"agent": "code_fixer", "event": "started"})

    branch_name = f"opsagentx/{state['incident_id'][:8]}-{uuid.uuid4().hex[:4]}"
    user_prompt = (
        f"Root-cause diagnosis:\n{state.get('diagnosis')}\n\n"
        f"Security findings:\n{state.get('security_findings')}\n\n"
        f"1. Create branch '{branch_name}'.\n"
        "2. Write the smallest safe unified diff that fixes the root cause without touching "
        "unrelated code.\n"
        "3. Apply it with code_patch.\n"
        "4. Reply with a one-paragraph summary of the fix."
    )
    summary, usage, _ = run_tool_agent(
        CODE_FIXER_SYSTEM_PROMPT, user_prompt, TOOLS_SCHEMA, _execute_tool, mode="think_max"
    )

    cost = estimate_cost_usd(usage, "think_max")
    publish_event(
        state["incident_id"],
        {"agent": "code_fixer", "event": "completed", "cost_usd": cost, "branch": branch_name},
    )

    token_usage = dict(state.get("token_usage", {}))
    token_usage["code_fixer"] = token_usage.get("code_fixer", 0) + usage.get("total_tokens", 0)

    return {
        "patch_diff": summary,
        "branch_name": branch_name,
        "status": "patch_generated",
        "token_usage": token_usage,
        "messages": [{"role": "assistant", "content": f"[code_fixer] {summary}"}],
    }
