import logging

from fastapi import APIRouter, HTTPException
from langgraph.types import Command

from app.agents.graph import get_compiled_graph
from app.db.mongo_client import incidents_async, update_incident_status
from app.models.schemas import ApprovalRequest

logger = logging.getLogger("opsagent.api.incidents")
router = APIRouter(prefix="/incidents", tags=["incidents"])


@router.get("")
async def list_incidents(limit: int = 50):
    cursor = incidents_async().find({}, {"_id": 0}).sort("incident_id", -1).limit(limit)
    return [doc async for doc in cursor]


@router.get("/{incident_id}")
async def get_incident(incident_id: str):
    doc = await incidents_async().find_one({"incident_id": incident_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Incident not found")

    graph = get_compiled_graph()
    snapshot = graph.get_state({"configurable": {"thread_id": incident_id}})
    doc["current_state"] = snapshot.values if snapshot else None
    doc["next_nodes"] = list(snapshot.next) if snapshot else []
    return doc


@router.post("/{incident_id}/approve")
def approve_incident(incident_id: str, approval: ApprovalRequest):
    """Resumes a graph paused at the human_approval interrupt."""
    graph = get_compiled_graph()
    config = {"configurable": {"thread_id": incident_id}}
    final_status = None
    for state in graph.stream(
        Command(resume={"approved": approval.approved, "reviewer": approval.reviewer, "note": approval.note}),
        config=config,
        stream_mode="values",
    ):
        status = state.get("status")
        if status:
            final_status = status
            update_incident_status(incident_id, status)
    return {"incident_id": incident_id, "status": final_status}
