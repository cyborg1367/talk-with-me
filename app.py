"""
app.py — FastAPI application entry point.

Run locally:
    uv run uvicorn app:app --reload --port 8000
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from agent.cyborg import Cyborg
from api.routes import router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger(__name__)

FRONTEND_DIR = Path(__file__).parent / "frontend"


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initialising Cyborg agent...")
    app.state.cyborg = Cyborg()
    logger.info("Cyborg ready — accepting requests.")
    yield
    logger.info("Shutting down.")


app = FastAPI(
    title="Talk With Me",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url=None,
)

app.include_router(router, prefix="/api", tags=["assistant"])

app.mount(
    "/",
    StaticFiles(directory=str(FRONTEND_DIR), html=True),
    name="static",
)