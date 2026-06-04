"""
auth/session.py — Session helpers and reusable FastAPI dependencies.

Sessions are stored in a signed cookie managed by Starlette's
SessionMiddleware (added to the app in app.py). The cookie contains a
small dict with the user's id, username, and avatar_url — enough to
identify the user without a DB round-trip on every request.

The current conversation id is also stored in the session so the
frontend can resume where it left off after a page refresh.
"""

from fastapi import Depends, HTTPException, Request


# ── Session keys ──────────────────────────────────────────────────────────

_KEY_USER    = "user"
_KEY_CONV_ID = "conv_id"


# ── Read helpers ──────────────────────────────────────────────────────────

def get_session_user(request: Request) -> dict | None:
    """Return the signed-in user dict from the session, or None."""
    return request.session.get(_KEY_USER)


def get_session_conv_id(request: Request) -> int | None:
    """Return the active conversation id from the session, or None."""
    return request.session.get(_KEY_CONV_ID)


# ── Write helpers ─────────────────────────────────────────────────────────

def set_session_user(request: Request, user: dict) -> None:
    """Persist the user dict in the session cookie."""
    request.session[_KEY_USER] = user


def set_session_conv_id(request: Request, conv_id: int) -> None:
    """Persist the active conversation id in the session cookie."""
    request.session[_KEY_CONV_ID] = conv_id


def clear_session(request: Request) -> None:
    """Wipe the entire session (logout)."""
    request.session.clear()


# ── FastAPI dependencies ──────────────────────────────────────────────────

def require_auth(request: Request) -> dict:
    """FastAPI dependency — raises 401 if the user is not signed in.

    Usage::

        @router.post("/api/chat/stream")
        async def chat(user: dict = Depends(require_auth)):
            ...
    """
    user = get_session_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required.")
    return user


def optional_auth(request: Request) -> dict | None:
    """FastAPI dependency — returns the user dict or None (no error).

    Use for endpoints that work both for guests and signed-in users.
    """
    return get_session_user(request)