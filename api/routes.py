"""
api/routes.py — FastAPI route handlers.

POST /api/chat/stream   Stream the assistant's reply as SSE (primary).
POST /api/chat          Return full reply as JSON (fallback).
POST /api/contact       Record a visitor's contact details directly (no LLM).
GET  /api/profile       Return profile metadata for the sidebar.
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


# ── Streaming endpoint (primary) ──────────────────────────────────────────

@router.post("/chat/stream", summary="Stream the assistant's reply via SSE")
async def chat_stream(request: Request, body: ChatRequest) -> StreamingResponse:
    """Stream the assistant's response as Server-Sent Events.

    Each event has the form:
        data: {"chunk": "..."}\n\n

    The stream ends with:
        data: [DONE]\n\n

    On error:
        data: {"error": "..."}\n\n

    Args:
        request: FastAPI request (carries ``app.state.cyborg``).
        body:    Validated chat payload.
    """
    cyborg = request.app.state.cyborg
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
            "Cache-Control": "no-cache",
            "Connection":    "keep-alive",
            # Tells nginx / HuggingFace proxy not to buffer the response.
            "X-Accel-Buffering": "no",
        },
    )


# ── Non-streaming fallback ────────────────────────────────────────────────

@router.post("/chat", response_model=ChatResponse, summary="Get the full reply as JSON")
async def chat(request: Request, body: ChatRequest) -> ChatResponse:
    """Return the complete assistant reply in one JSON response.

    Kept as a fallback for environments where streaming is unavailable.
    """
    cyborg = request.app.state.cyborg
    history = [msg.model_dump() for msg in body.history]

    try:
        response: str = await asyncio.to_thread(cyborg.chat, body.message, history)
    except Exception as exc:
        logger.error("Cyborg.chat error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="The assistant encountered an error.")

    return ChatResponse(response=response)


# ── Contact capture (no LLM) ─────────────────────────────────────────────

@router.post("/contact", response_model=ContactResponse, summary="Record visitor contact details")
async def record_contact(body: ContactRequest) -> ContactResponse:
    """Record a visitor's name and email and fire a Pushover notification.

    Calls ``record_user_details`` directly — no LLM round-trip — so the
    notification is instant and reliable regardless of model availability.

    Args:
        body: Validated contact payload from the frontend CTA card.

    Returns:
        Success confirmation shown to the visitor.

    Raises:
        HTTPException 500: If the Pushover call fails.
    """
    try:
        await asyncio.to_thread(
            record_user_details,
            email=body.email,
            name=body.name,
            notes=body.notes or "Submitted via website chat CTA",
        )
    except Exception as exc:
        logger.error("Contact recording failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to send your message. Please try again.")

    return ContactResponse(success=True)


# ── Profile ───────────────────────────────────────────────────────────────

@router.get("/profile", response_model=ProfileResponse, summary="Get profile display metadata")
async def get_profile() -> ProfileResponse:
    """Return structured profile data for the frontend sidebar."""
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