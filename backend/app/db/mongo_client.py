"""
MongoDB stores the durable record of each incident and the verification
audit trail (compliance metrics, configuration history). FastAPI route
handlers are async, so they use Motor. Graph nodes are sync, so they use
PyMongo directly.
"""

from functools import lru_cache

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import MongoClient

from app.config import settings


@lru_cache
def get_mongo_async() -> AsyncIOMotorClient:
    return AsyncIOMotorClient(settings.MONGO_URI)


@lru_cache
def get_mongo_sync() -> MongoClient:
    return MongoClient(settings.MONGO_URI)


def db_async():
    return get_mongo_async()[settings.MONGO_DB_NAME]


def db_sync():
    return get_mongo_sync()[settings.MONGO_DB_NAME]


def incidents_async():
    return db_async()["incidents"]


def incidents_sync():
    return db_sync()["incidents"]


def update_incident_status(incident_id: str, status: str) -> None:
    """Mirrors the graph's live `status` into the Mongo record so the
    dashboard's incident list (which only reads Mongo, not the graph
    checkpoint) reflects progress instead of being stuck on 'received'."""
    incidents_sync().update_one({"incident_id": incident_id}, {"$set": {"status": status}})


def audit_sync():
    """Verification results + retry history — the compliance/audit trail."""
    return db_sync()["audit_logs"]
