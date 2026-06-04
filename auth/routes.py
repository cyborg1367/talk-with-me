"""
auth/routes.py — FastAPI routes for the HuggingFace OAuth flow.

GET /auth/login      → redirect to HuggingFace authorisation page
GET /auth/callback   → handle the code, create session, redirect to /
GET /auth/logout     → clear session, redirect to /
GET /auth/me         → return current user info (or {authenticated: false})
"""

import logging
import secrets

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse

from auth.oauth import exchange_code, get_auth_url, get_userinfo, is_oauth_configured
from auth.session import (
    clear_session,
    get_session_user,
    set_session_user,
)
from db.database import get_db
from db.queries import upsert_user

logger = logging.getLogger(__name__)
router = APIRouter()


def _build_redirect_uri(request: Request) -> str:
    """Derive the OAuth callback URL from the incoming request.

    Uses ``x-forwarded-proto`` and ``x-forwarded-host`` when present so
    the URI is correct behind HuggingFace's reverse proxy (which terminates
    TLS and forwards as HTTP internally).
    """
    proto = request.headers.get("x-forwarded-proto") or request.url.scheme
    host  = request.headers.get("x-forwarded-host") or request.headers.get("host") or request.url.netloc
    return f"{proto}://{host}/auth/callback"


# ── Login ─────────────────────────────────────────────────────────────────

@router.get("/login", summary="Redirect to HuggingFace login")
async def login(request: Request) -> RedirectResponse:
    """Generate a CSRF state token, store it in the session, and redirect
    the user to HuggingFace's OAuth authorisation page.
    """
    if not is_oauth_configured():
        raise HTTPException(
            status_code=503,
            detail="OAuth is not configured. This feature is only available on HuggingFace Spaces.",
        )

    state        = secrets.token_urlsafe(32)
    redirect_uri = _build_redirect_uri(request)

    # Store both state (CSRF) and redirect_uri so the callback can use
    # the exact same URI — HuggingFace requires they match precisely.
    request.session["oauth_state"]       = state
    request.session["oauth_redirect_uri"] = redirect_uri

    logger.info("OAuth login → redirect_uri: %s", redirect_uri)

    return RedirectResponse(get_auth_url(state, redirect_uri))


# ── Callback ──────────────────────────────────────────────────────────────

@router.get("/callback", summary="Handle OAuth callback from HuggingFace")
async def callback(
    request: Request,
    code: str,
    state: str,
) -> RedirectResponse:
    """Handle the redirect from HuggingFace after the user authorises.

    Steps:
        1. Verify the CSRF state token.
        2. Exchange the authorisation code for an access token.
        3. Fetch the user's profile.
        4. Upsert the user in SQLite.
        5. Write the user to the session cookie.
        6. Redirect to the home page.
    """
    # ① Verify CSRF state
    expected_state = request.session.pop("oauth_state", None)
    if not expected_state or state != expected_state:
        logger.warning("OAuth callback: invalid state parameter")
        raise HTTPException(status_code=400, detail="Invalid OAuth state. Please try signing in again.")

    # ② Retrieve the redirect_uri stored during /auth/login
    redirect_uri = request.session.pop("oauth_redirect_uri", None) or _build_redirect_uri(request)

    # ③ Exchange code for token
    try:
        token_data   = await exchange_code(code, redirect_uri)
        access_token = token_data["access_token"]
    except Exception as exc:
        logger.error("OAuth token exchange failed: %s", exc)
        raise HTTPException(status_code=502, detail="Failed to exchange OAuth code. Please try again.")

    # ④ Fetch user profile
    try:
        userinfo = await get_userinfo(access_token)
    except Exception as exc:
        logger.error("OAuth userinfo fetch failed: %s", exc)
        raise HTTPException(status_code=502, detail="Failed to fetch user profile. Please try again.")

    # ⑤ Upsert user in the database
    with get_db() as db:
        user = upsert_user(
            db,
            id=userinfo["sub"],
            username=userinfo.get("preferred_username", userinfo["sub"]),
            avatar_url=userinfo.get("picture", ""),
            email=userinfo.get("email", ""),
        )

    # ⑥ Write minimal user info to the session cookie
    set_session_user(request, {
        "id":         user.id,
        "username":   user.username,
        "avatar_url": user.avatar_url,
    })

    logger.info("User signed in: %s", user.username)

    # ⑦ Redirect to home
    return RedirectResponse("/", status_code=302)


# ── Logout ────────────────────────────────────────────────────────────────

@router.get("/logout", summary="Sign out and clear the session")
async def logout(request: Request) -> RedirectResponse:
    """Clear the session cookie and redirect to the home page."""
    username = (get_session_user(request) or {}).get("username", "unknown")
    clear_session(request)
    logger.info("User signed out: %s", username)
    return RedirectResponse("/", status_code=302)


# ── Me ────────────────────────────────────────────────────────────────────

@router.get("/me", summary="Return the current user's session info")
async def me(request: Request) -> JSONResponse:
    """Return the signed-in user's info, or ``{authenticated: false}``.

    Called by the frontend on page load to determine whether to show
    the name overlay or load the user's conversation history.

    Returns:
        JSON with ``authenticated`` bool and, if signed in, the user's
        ``id``, ``username``, and ``avatar_url``.
    """
    user = get_session_user(request)
    if not user:
        return JSONResponse({"authenticated": False})

    return JSONResponse({
        "authenticated": True,
        "id":            user["id"],
        "username":      user["username"],
        "avatar_url":    user.get("avatar_url", ""),
    })