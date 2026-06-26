"""
Trivy-backed vulnerability scanning for the SecurityAgent.

Requires the `trivy` binary on PATH (installed in backend/Dockerfile). This
tool only ever reads scan results — it cannot quarantine images, kill pods,
or otherwise act on what it finds; that's left to CodeFixer + human review.
"""

import json
import logging
import subprocess

logger = logging.getLogger("opsagent.tools.security")


def trivy_scan(image: str) -> str:
    """Tool: run a Trivy CRITICAL/HIGH vulnerability scan against a container image."""
    try:
        result = subprocess.run(
            ["trivy", "image", "--quiet", "--format", "json", "--severity", "CRITICAL,HIGH", image],
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )
        if result.returncode not in (0, 1):
            return f"ERROR running trivy: {result.stderr.strip()}"

        report = json.loads(result.stdout or "{}")
        findings = []
        for target in report.get("Results", []) or []:
            for vuln in target.get("Vulnerabilities", []) or []:
                findings.append(f"{vuln.get('VulnerabilityID')} ({vuln.get('Severity')}) in {vuln.get('PkgName')}")

        if not findings:
            return "No CRITICAL/HIGH vulnerabilities found."
        return "Found vulnerabilities:\n" + "\n".join(findings[:30])
    except FileNotFoundError:
        return "ERROR: trivy binary not found in this container."
    except Exception as exc:  # noqa: BLE001
        logger.exception("trivy_scan failed")
        return f"ERROR running trivy scan: {exc}"
