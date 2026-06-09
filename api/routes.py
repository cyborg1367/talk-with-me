"""
api/routes.py — FastAPI route handlers.

POST /api/chat/stream   Stream assistant reply as SSE.
POST /api/chat          Full reply as JSON (streaming fallback).
POST /api/contact       Record visitor contact details.
GET  /api/profile       Profile metadata for the sidebar.
"""

import asyncio
import json
import logging

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from api.models import ChatRequest, ChatResponse, ContactRequest, ContactResponse, ProfileResponse
from profile_meta import profile_meta
from tools.functions import record_user_details

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/chat/stream", summary="Stream the assistant's reply via SSE")
async def chat_stream(request: Request, body: ChatRequest) -> StreamingResponse:
    cyborg  = request.app.state.cyborg
    history = [msg.model_dump() for msg in body.history]

    async def event_stream():
        try:
            async for chunk in cyborg.chat_stream(body.message, history):
                yield f"data: {json.dumps({'chunk': chunk})}\n\n"
        except Exception as exc:
            logger.error("Streaming error: %s", exc, exc_info=True)
            yield f"data: {json.dumps({'error': str(exc)})}\n\n"
        finally:
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control":     "no-cache",
            "Connection":        "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/chat", response_model=ChatResponse, summary="Get full reply as JSON")
async def chat(request: Request, body: ChatRequest) -> ChatResponse:
    cyborg  = request.app.state.cyborg
    history = [msg.model_dump() for msg in body.history]
    try:
        response: str = await asyncio.to_thread(cyborg.chat, body.message, history)
    except Exception as exc:
        logger.error("Cyborg.chat error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="The assistant encountered an error.")
    return ChatResponse(response=response)


@router.post("/contact", response_model=ContactResponse, summary="Record visitor contact")
async def record_contact(body: ContactRequest) -> ContactResponse:
    try:
        await asyncio.to_thread(
            record_user_details,
            email=body.email,
            name=body.name,
            notes=body.notes or "Submitted via website chat CTA",
        )
    except Exception as exc:
        logger.error("Contact recording failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to send. Please try again.")
    return ContactResponse(success=True)


@router.get("/profile", response_model=ProfileResponse, summary="Get profile metadata")
async def get_profile() -> ProfileResponse:
    return ProfileResponse(
        name=profile_meta.name,
        initials=profile_meta.initials,
        title=profile_meta.title,
        tagline=profile_meta.tagline,
        skills=list(profile_meta.skills),
        linkedin_url=profile_meta.linkedin_url,
        github_url=profile_meta.github_url,
        email=profile_meta.email,
        status=profile_meta.status,
        suggested_questions=list(profile_meta.suggested_questions),
    )


@router.get("/projects", summary="Get all portfolio projects")
async def get_projects() -> list:
    """Return the projects.json list for the portfolio showcase page."""
    import json
    from pathlib import Path
    from config import settings

    path = Path(settings.projects_json)
    if not path.exists():
        return []
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return []