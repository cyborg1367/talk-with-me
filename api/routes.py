"""
api/routes.py — All FastAPI route handlers.

Endpoints
─────────
POST /api/chat/stream          Stream assistant reply as SSE (primary).
POST /api/chat                 Full reply as JSON (streaming fallback).
POST /api/contact              Record visitor contact details directly.
GET  /api/profile              Profile metadata for the sidebar.
POST /api/conversations        Create a new conversation (auth required).
GET  /api/conversations        List user's conversations (auth required).
GET  /api/conversations/{id}   Load messages for a conversation (auth required).

Persistence
───────────
Messages are saved to SQLite only when:
  - The user is signed in (session contains a user dict), AND
  - The request includes a valid conv_id.
Guest users get full chat functionality; nothing is stored.
"""

import asyncio
import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from api.models import (
    ChatRequest,
    ChatResponse,
    ContactRequest,
    ContactResponse,
    ConversationOut,
    MessageOut,
    NewConversationResponse,
    ProfileResponse,
)
from auth.session import optional_auth, require_auth
from db.database import get_db
from db.queries import (
    add_message,
    create_conversation,
    get_conversation,
    get_conversation_messages,
    get_user_conversations,
    touch_conversation,
    update_conversation_title,
    upsert_user,
)
from profile_meta import profile_meta
from tools.functions import record_user_details

logger = logging.getLogger(__name__)
router = APIRouter()


# ═══════════════════════════════════════════════════════════════════════════
# STREAMING CHAT  (primary)
# ═══════════════════════════════════════════════════════════════════════════

@router.post("/chat/stream", summary="Stream the assistant's reply via SSE")
async def chat_stream(
    request: Request,
    body: ChatRequest,
    user: dict | None = Depends(optional_auth),
) -> StreamingResponse:
    """Stream the assistant's response as Server-Sent Events.

    If the user is signed in and ``body.conv_id`` is provided, messages
    are saved to SQLite — user message before streaming starts, bot
    response after the stream completes.

    SSE format:
        data: {"chunk": "..."}\n\n   — each text token
        data: [DONE]\n\n             — end of stream
        data: {"error": "..."}\n\n   — on failure
    """
    cyborg   = request.app.state.cyborg
    history  = [msg.model_dump() for msg in body.history]
    conv_id  = body.conv_id
    save     = bool(user and conv_id)   # only persist for signed-in users

    async def event_stream():
        full_response = ""

        # ── Save user message before streaming ────────────────────────────
        if save:
            try:
                with get_db() as db:
                    # Set conversation title from the first real message
                    conv = get_conversation(db, id=conv_id)
                    if conv and conv.title == "New conversation":
                        title = body.message[:60].strip().replace("\n", " ")
                        update_conversation_title(db, conv_id=conv_id, title=title)
                    add_message(db, conv_id=conv_id, role="user", content=body.message)
            except Exception as exc:
                logger.error("Failed to save user message: %s", exc)

        # ── Stream bot response ───────────────────────────────────────────
        try:
            async for chunk in cyborg.chat_stream(body.message, history):
                full_response += chunk
                yield f"data: {json.dumps({'chunk': chunk})}\n\n"

        except Exception as exc:
            logger.error("Streaming error: %s", exc, exc_info=True)
            yield f"data: {json.dumps({'error': str(exc)})}\n\n"

        finally:
            yield "data: [DONE]\n\n"

            # ── Save bot response after stream completes ──────────────────
            if save and full_response:
                try:
                    with get_db() as db:
                        add_message(
                            db,
                            conv_id=conv_id,
                            role="assistant",
                            content=full_response,
                        )
                        touch_conversation(db, conv_id=conv_id)
                except Exception as exc:
                    logger.error("Failed to save bot response: %s", exc)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control":     "no-cache",
            "Connection":        "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ═══════════════════════════════════════════════════════════════════════════
# NON-STREAMING FALLBACK
# ═══════════════════════════════════════════════════════════════════════════

@router.post("/chat", response_model=ChatResponse, summary="Get full reply as JSON")
async def chat(
    request: Request,
    body: ChatRequest,
    user: dict | None = Depends(optional_auth),
) -> ChatResponse:
    """Return the complete assistant reply in one JSON response.

    Kept as a fallback for environments where streaming is unavailable.
    Also saves messages to SQLite for signed-in users.
    """
    cyborg  = request.app.state.cyborg
    history = [msg.model_dump() for msg in body.history]
    save    = bool(user and body.conv_id)

    try:
        response: str = await asyncio.to_thread(cyborg.chat, body.message, history)
    except Exception as exc:
        logger.error("Cyborg.chat error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="The assistant encountered an error.")

    # Persist for signed-in users
    if save:
        try:
            with get_db() as db:
                conv = get_conversation(db, id=body.conv_id)
                if conv and conv.title == "New conversation":
                    title = body.message[:60].strip().replace("\n", " ")
                    update_conversation_title(db, conv_id=body.conv_id, title=title)
                add_message(db, conv_id=body.conv_id, role="user",      content=body.message)
                add_message(db, conv_id=body.conv_id, role="assistant", content=response)
                touch_conversation(db, conv_id=body.conv_id)
        except Exception as exc:
            logger.error("Failed to persist chat messages: %s", exc)

    return ChatResponse(response=response)


# ═══════════════════════════════════════════════════════════════════════════
# CONVERSATION HISTORY
# ═══════════════════════════════════════════════════════════════════════════

@router.post(
    "/conversations",
    response_model=NewConversationResponse,
    summary="Create a new conversation",
)
async def new_conversation(
    user: dict = Depends(require_auth),
) -> NewConversationResponse:
    """Create a fresh conversation row for the signed-in user.

    The frontend calls this once when the user starts a new chat session,
    then passes the returned ``id`` as ``conv_id`` in every chat request.
    """
    with get_db() as db:
        conv = create_conversation(db, user_id=user["id"])
    return NewConversationResponse(id=conv.id, title=conv.title)


@router.get(
    "/conversations",
    response_model=list[ConversationOut],
    summary="List user's conversations",
)
async def list_conversations(
    user: dict = Depends(require_auth),
) -> list[ConversationOut]:
    """Return the signed-in user's conversations, most recent first.

    Used to populate the history sidebar / dropdown in the frontend.
    """
    with get_db() as db:
        convs = get_user_conversations(db, user_id=user["id"])
    return [
        ConversationOut(
            id=c.id,
            title=c.title,
            started_at=c.started_at,
            updated_at=c.updated_at,
        )
        for c in convs
    ]


@router.get(
    "/conversations/{conv_id}",
    response_model=list[MessageOut],
    summary="Load messages for a conversation",
)
async def get_messages(
    conv_id: int,
    user: dict = Depends(require_auth),
) -> list[MessageOut]:
    """Return all messages for a conversation in chronological order.

    The frontend calls this when the user selects a past conversation
    to resume. Returns 404 if the conversation doesn't belong to the user.
    """
    with get_db() as db:
        conv = get_conversation(db, id=conv_id)

        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found.")

        if conv.user_id != user["id"]:
            raise HTTPException(status_code=403, detail="Access denied.")

        messages = get_conversation_messages(db, conv_id=conv_id)

    return [
        MessageOut(
            id=m.id,
            role=m.role,
            content=m.content,
            created_at=m.created_at,
        )
        for m in messages
    ]


# ═══════════════════════════════════════════════════════════════════════════
# CONTACT CTA
# ═══════════════════════════════════════════════════════════════════════════

@router.post("/contact", response_model=ContactResponse, summary="Record visitor contact")
async def record_contact(body: ContactRequest) -> ContactResponse:
    """Record a visitor's contact details and fire a Pushover notification."""
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


# ═══════════════════════════════════════════════════════════════════════════
# PROFILE
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/profile", response_model=ProfileResponse, summary="Get profile metadata")
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