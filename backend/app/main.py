import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.agents.graph import init_graph, shutdown_graph
from app.api import routes_incidents, routes_stream, routes_webhook
from app.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("opsagent")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Booting OpsAgent-X backend (env=%s)", settings.ENVIRONMENT)
    init_graph()
    yield
    shutdown_graph()


app = FastAPI(title="OpsAgent-X", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_ORIGIN],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(routes_webhook.router)
app.include_router(routes_incidents.router)
app.include_router(routes_stream.router)


@app.get("/health")
def health():
    return {"status": "ok", "environment": settings.ENVIRONMENT}
