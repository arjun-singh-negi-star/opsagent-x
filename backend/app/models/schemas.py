from typing import Any

from pydantic import BaseModel, Field


class AlertWebhookPayload(BaseModel):
    """Generic shape that covers Alertmanager, Datadog, and most other
    webhook senders — map your provider's payload to this in the upstream
    config, or extend it directly."""

    source: str = Field(..., description="Alert source, e.g. 'alertmanager', 'datadog'")
    severity: str = "warning"
    service: str | None = None
    namespace: str | None = None
    image: str | None = None
    summary: str
    raw: dict[str, Any] = Field(default_factory=dict)


class ApprovalRequest(BaseModel):
    approved: bool
    reviewer: str | None = None
    note: str | None = None
