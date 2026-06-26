import logging
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks

from app.agents.graph import get_compiled_graph
from app.db.mongo_client import incidents_sync, update_incident_status
from app.db.redis_client import publish_event
from app.models.schemas import AlertWebhookPayload

logger = logging.getLogger("opsagent.api.webhook")
router = APIRouter(prefix="/webhook", tags=["webhook"])


def _run_workflow(incident_id: str, alert: dict) -> None:
    """Runs synchronously — FastAPI's BackgroundTasks executes sync callables
    in a thread pool, so this doesn't block the event loop."""
    graph = get_compiled_graph()
    config = {"configurable": {"thread_id": incident_id}}
    initial_state = {
        "incident_id": incident_id,
        "raw_alert": alert,
        "retry_count": 0,
        "status": "received",
        "token_usage": {},
        "messages": [],
    }
    try:
        for state in graph.stream(initial_state, config=config, stream_mode="values"):
            status = state.get("status")
            if status:
                update_incident_status(incident_id, status)
    except Exception:  # noqa: BLE001
        logger.exception("Workflow failed for incident %s", incident_id)
        update_incident_status(incident_id, "error")
        publish_event(incident_id, {"agent": "graph", "event": "error"})


@router.post("/alert", status_code=202)
def receive_alert(payload: AlertWebhookPayload, background_tasks: BackgroundTasks):
    incident_id = str(uuid4())
    alert = payload.model_dump()

    incidents_sync().insert_one({"incident_id": incident_id, "alert": alert, "status": "received"})

    background_tasks.add_task(_run_workflow, incident_id, alert)
    return {"incident_id": incident_id, "status": "accepted"}
