import logging

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.db.redis_client import get_redis_async

logger = logging.getLogger("opsagent.api.stream")
router = APIRouter(prefix="/incidents", tags=["stream"])

HEARTBEAT_SECONDS = 15.0


async def _event_generator(incident_id: str, last_event_id: int | None):
    """
    Streams the incident's event history, then live updates.

    Every event gets an SSE `id:` matching its position in the durable
    Redis list. Browsers remember the last id they saw and automatically
    send it back as a `Last-Event-ID` header on reconnect — so if the
    connection ever does drop and reconnect, we resume from there instead
    of replaying the entire history again (which is what was causing the
    timeline to repeat itself).

    We also emit a `: keep-alive` comment every HEARTBEAT_SECONDS of
    silence. SSE comments are ignored by EventSource's onmessage handler,
    but they keep the connection from going idle and being silently
    reconnected by the browser in the first place — the actual root cause
    of the duplication.
    """
    redis_client = get_redis_async()
    timeline_key = f"incident:{incident_id}:timeline"

    start_index = (last_event_id + 1) if last_event_id is not None else 0
    timeline = await redis_client.lrange(timeline_key, start_index, -1)
    for offset, item in enumerate(timeline):
        yield f"id: {start_index + offset}\ndata: {item}\n\n"

    next_index = start_index + len(timeline)

    pubsub = redis_client.pubsub()
    await pubsub.subscribe(f"incident:{incident_id}:events")
    try:
        while True:
            message = await pubsub.get_message(timeout=HEARTBEAT_SECONDS)
            if message is None:
                yield ": keep-alive\n\n"
                continue
            if message["type"] != "message":
                continue
            yield f"id: {next_index}\ndata: {message['data']}\n\n"
            next_index += 1
    finally:
        await pubsub.unsubscribe(f"incident:{incident_id}:events")


@router.get("/{incident_id}/stream")
async def stream_incident(incident_id: str, request: Request):
    raw_last_id = request.headers.get("last-event-id")
    last_event_id = int(raw_last_id) if raw_last_id and raw_last_id.isdigit() else None
    return StreamingResponse(
        _event_generator(incident_id, last_event_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
