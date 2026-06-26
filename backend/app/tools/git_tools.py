"""
Git tools for the CodeFixer agent.

Safety constraints, both enforced in code (not just by prompting):
  * code_patch refuses any file_path that resolves outside the repo root.
  * Neither tool ever pushes or merges. CodeFixer can only create a local
    feature branch and commit to it. Getting that branch deployed requires
    Verification to pass AND a human to approve it on the dashboard
    (see agents/graph.py).
"""

import logging
import subprocess
from pathlib import Path

from app.config import settings

logger = logging.getLogger("opsagent.tools.git")


def git_create_branch(branch_name: str) -> str:
    """Tool: create and check out a new branch off origin/main for this incident's fix."""
    repo = Path(settings.GIT_REPO_PATH)
    try:
        subprocess.run(["git", "fetch", "origin"], cwd=repo, check=True, capture_output=True, text=True)
        subprocess.run(
            ["git", "checkout", "-B", branch_name, "origin/main"],
            cwd=repo,
            check=True,
            capture_output=True,
            text=True,
        )
        return f"Branch '{branch_name}' created from origin/main."
    except subprocess.CalledProcessError as exc:
        return f"ERROR creating branch: {exc.stderr}"


def code_patch(file_path: str, unified_diff: str) -> str:
    """Tool: apply a unified diff to ONE file inside the repo and commit it
    to the current branch. Never pushes or merges."""
    repo = Path(settings.GIT_REPO_PATH).resolve()
    target = (repo / file_path).resolve()
    if repo != target and repo not in target.parents:
        return "DENIED: file_path escapes the repository root."

    patch_file = repo / ".opsagentx_patch.diff"
    patch_file.write_text(unified_diff)
    try:
        subprocess.run(
            ["git", "apply", "--whitespace=fix", str(patch_file)],
            cwd=repo,
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(["git", "add", file_path], cwd=repo, check=True, capture_output=True, text=True)
        subprocess.run(
            ["git", "commit", "-m", f"OpsAgent-X: automated patch for {file_path}"],
            cwd=repo,
            check=True,
            capture_output=True,
            text=True,
        )
        return f"Patch applied and committed for {file_path}."
    except subprocess.CalledProcessError as exc:
        return f"ERROR applying patch: {exc.stderr}"
    finally:
        patch_file.unlink(missing_ok=True)
