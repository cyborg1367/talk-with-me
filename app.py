"""
app.py — FastAPI application entry point.

Serves:
    /auth/*        HuggingFace OAuth flow
    /api/*         REST + SSE API
    /              Static frontend (index.html + assets)

Run locally:
    uv run uvicorn app:app --reload --port 8000

Deploy on HuggingFace Spaces (Docker SDK) — must listen on port 7860.
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from agent.cyborg import Cyborg
from api.routes import router as api_router
from auth.routes import router as auth_router
from config import settings
from db.database import init_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger(__name__)

FRONTEND_DIR = Path(__file__).parent / "frontend"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialise the database and load the Cyborg agent at startup."""
    logger.info("Initialising database...")
    init_db()
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
    docs_url="/api/docs",
    redoc_url=None,
)

# ── Session middleware ────────────────────────────────────────────────────
# Must be added BEFORE the routers so the session is available in all routes.
# The secret key signs the cookie — change SESSION_SECRET in production.
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.session_secret,
    session_cookie="twm_session",
    max_age=60 * 60 * 24 * 30,  # 30 days
    https_only=False,            # set True in production (HF uses HTTPS)
    same_site="lax",
)

# ── Routers ───────────────────────────────────────────────────────────────
# Auth routes at /auth/* — before API so session is populated first
app.include_router(auth_router, prefix="/auth", tags=["auth"])

# API routes at /api/*
app.include_router(api_router, prefix="/api", tags=["assistant"])

# ── Frontend static files (catch-all — must be last) ─────────────────────
app.mount(
    "/",
    StaticFiles(directory=str(FRONTEND_DIR), html=True),
    name="static",
)