"""
app.py — FastAPI application entry point.

Serves the REST API on /api/* and the static frontend on everything else.
Run locally:
    uv run uvicorn app:app --reload --port 8000
Deploy on HuggingFace Spaces (Docker SDK) — must listen on port 7860.
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
    """Load the Cyborg agent once at startup and keep it in app state."""
    logger.info("Initialising Cyborg agent...")
    app.state.cyborg = Cyborg()
    logger.info("Cyborg ready — accepting requests.")
    yield
    logger.info("Shutting down.")


app = FastAPI(
    title="Talk With Me",
    description="Personal AI assistant API",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",   # Swagger UI
    redoc_url=None,
)

# ── API routes — must be registered before the static-files catch-all ──────
app.include_router(router, prefix="/api", tags=["assistant"])

# ── Frontend — serves index.html for / and all unmatched paths (SPA) ───────
app.mount(
    "/",
    StaticFiles(directory=str(FRONTEND_DIR), html=True),
    name="static",
)
