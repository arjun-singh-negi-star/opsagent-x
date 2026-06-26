"""
Redis is used for three things in OpsAgent-X:

1. LangGraph checkpointing (state survives a pod crash — see agents/graph.py)
2. Live event pub/sub so the Next.js dashboard can stream agent progress
3. (Optionally) semantic caching of repeated K8s/log queries to save LLM calls

Graph nodes are plain sync functions (they shell out to git/trivy/kubectl-style
SDKs), so they use the sync client. The SSE endpoint that streams to the
browser is async, so it uses the async client.
"""

import json
from functools import lru_cache

import redis
import redis.asyncio as aioredis

from app.config import settings


@lru_cache
def get_redis_sync() -> redis.Redis:
    return redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)


@lru_cache
def get_redis_async() -> aioredis.Redis:
    return aioredis.Redis.from_url(settings.REDIS_URL, decode_responses=True)


def publish_event(incident_id: str, event: dict) -> None:
    """Called from graph nodes (sync). Publishes a live event AND appends it
    to a durable list, so the dashboard can replay history on page load and
    then keep listening for new events."""
    r = get_redis_sync()
    payload = json.dumps(event)
    timeline_key = f"incident:{incident_id}:timeline"
    r.publish(f"incident:{incident_id}:events", payload)
    r.rpush(timeline_key, payload)
    r.expire(timeline_key, 60 * 60 * 24 * 7)  # 7 days
