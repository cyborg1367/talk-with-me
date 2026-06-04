"""
auth/routes.py — Simple email-based identification (no OAuth).

POST /auth/identify   Submit name + email, create session, return user info.
GET  /auth/me         Return current session user or {authenticated: false}.
GET  /auth/logout     Clear session and redirect to /.
"""

import logging

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, EmailStr, Field

from auth.session import clear_session, get_session_user, set_session_user
from db.database import get_db
from db.queries import upsert_user

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Pydantic models ───────────────────────────────────────────────────────

class IdentifyRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=100, description="Display name")
    email:    str = Field(..., min_length=5, max_length=200, description="Email address")


class IdentifyResponse(BaseModel):
    success:  bool
    username: str
    id:       str


# ── Routes ────────────────────────────────────────────────────────────────

@router.post("/identify", response_model=IdentifyResponse, summary="Identify visitor by name + email")
async def identify(request: Request, body: IdentifyRequest) -> IdentifyResponse:
    """Create or update a user record and write a session cookie.

    Uses the lowercased email as the stable user id so returning visitors
    automatically resume their conversation history.

    Args:
        body: ``{username, email}`` submitted from the welcome form.
    """
    user_id = body.email.strip().lower()

    with get_db() as db:
        user = upsert_user(
            db,
            id=user_id,
            username=body.username.strip(),
            email=user_id,
        )

    set_session_user(request, {
        "id":         user.id,
        "username":   user.username,
        "avatar_url": "",
    })

    logger.info("User identified: %s (%s)", user.username, user.id)
    return IdentifyResponse(success=True, username=user.username, id=user.id)


@router.get("/me", summary="Return current session user")
async def me(request: Request) -> JSONResponse:
    """Return the signed-in user's session info or ``{authenticated: false}``."""
    user = get_session_user(request)
    if not user:
        return JSONResponse({"authenticated": False})
    return JSONResponse({
        "authenticated": True,
        "id":            user["id"],
        "username":      user["username"],
        "avatar_url":    user.get("avatar_url", ""),
    })


@router.get("/logout", summary="Clear session and redirect to /")
async def logout(request: Request) -> RedirectResponse:
    """Clear the session cookie and send the user back to the welcome form."""
    username = (get_session_user(request) or {}).get("username", "unknown")
    clear_session(request)
    logger.info("User signed out: %s", username)
    return RedirectResponse("/", status_code=302)