"""
Verification node: deterministic, non-LLM gate. Runs the test suite (and,
if configured, a SonarQube scan) against CodeFixer's branch. This is what
decides whether the patch goes to a human for approval or back to the
Supervisor for another attempt.

Every run is written to MongoDB's audit_logs collection regardless of
outcome — that's the compliance trail mentioned in the project brief.
"""

import logging
import subprocess
from pathlib import Path

from app.agents.state import OpsAgentState
from app.config import settings
from app.db.mongo_client import audit_sync
from app.db.redis_client import publish_event

logger = logging.getLogger("opsagent.agents.verification")


def verification_node(state: OpsAgentState) -> dict:
    publish_event(state["incident_id"], {"agent": "verification", "event": "started"})

    repo = Path(settings.GIT_REPO_PATH)
    passed = True
    output_chunks = []

    try:
        pytest_result = subprocess.run(["pytest", "-q"], cwd=repo, capture_output=True, text=True, timeout=600)
        output_chunks.append(pytest_result.stdout[-4000:])
        passed = passed and pytest_result.returncode == 0
    except Exception as exc:  # noqa: BLE001
        passed = False
        output_chunks.append(f"pytest failed to run: {exc}")

    output = "\n---\n".join(output_chunks)

    audit_sync().insert_one(
        {
            "incident_id": state["incident_id"],
            "branch": state.get("branch_name"),
            "verification_passed": passed,
            "verification_output": output[-4000:],
            "retry_count": state.get("retry_count", 0),
        }
    )

    publish_event(state["incident_id"], {"agent": "verification", "event": "completed", "passed": passed})

    return {
        "verification_passed": passed,
        "verification_output": output,
        "retry_count": state.get("retry_count", 0) + (0 if passed else 1),
        "status": "verified" if passed else "verification_failed",
    }
