"""
auth/oauth.py — HuggingFace OAuth 2.0 helpers.

HuggingFace Spaces with ``hf_oauth: true`` in README.md automatically
inject two environment variables:
    OAUTH_CLIENT_ID      — the app's client id
    OAUTH_CLIENT_SECRET  — the app's client secret

The full flow:
    1. Redirect user to HF_AUTH_URL with client_id, redirect_uri, state.
    2. User authorises on HuggingFace.
    3. HF redirects back to /auth/callback?code=...&state=...
    4. Exchange the code for a token via HF_TOKEN_URL.
    5. Fetch the user's profile via HF_USERINFO_URL.
"""

import logging
from urllib.parse import urlencode

import httpx

from config import settings

logger = logging.getLogger(__name__)

# ── HuggingFace OAuth endpoints ───────────────────────────────────────────

HF_AUTH_URL     = "https://huggingface.co/oauth/authorize"
HF_TOKEN_URL    = "https://huggingface.co/oauth/token"
HF_USERINFO_URL = "https://huggingface.co/oauth/userinfo"


# ── Public helpers ────────────────────────────────────────────────────────

def is_oauth_configured() -> bool:
    """Return True if the OAuth credentials are present.

    On HuggingFace Spaces these are injected automatically.
    Locally they are absent, so OAuth is disabled.
    """
    return bool(settings.hf_oauth_client_id and settings.hf_oauth_client_secret)


def get_auth_url(state: str, redirect_uri: str) -> str:
    """Build the HuggingFace authorisation URL.

    Args:
        state:        A random CSRF token stored in the session.
        redirect_uri: The absolute callback URL (built from the request).

    Returns:
        Full URL to redirect the user to for login.
    """
    params = {
        "client_id":     settings.hf_oauth_client_id,
        "redirect_uri":  redirect_uri,
        "scope":         "openid profile",
        "response_type": "code",
        "state":         state,
    }
    return f"{HF_AUTH_URL}?{urlencode(params)}"


async def exchange_code(code: str, redirect_uri: str) -> dict:
    """Exchange an authorisation code for an access token.

    Args:
        code:         The ``code`` query parameter from the OAuth callback.
        redirect_uri: Must exactly match the URI used in the auth request.
    """
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            HF_TOKEN_URL,
            data={
                "grant_type":    "authorization_code",
                "code":          code,
                "redirect_uri":  redirect_uri,
                "client_id":     settings.hf_oauth_client_id,
                "client_secret": settings.hf_oauth_client_secret,
            },
            headers={"Accept": "application/json"},
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()


async def get_userinfo(access_token: str) -> dict:
    """Fetch the authenticated user's profile from HuggingFace.

    The returned dict includes at minimum:
        ``sub``                  — the user's unique HF id
        ``preferred_username``   — the user's HF username
        ``picture``              — avatar URL (may be absent)
        ``email``                — email address (may be absent)

    Args:
        access_token: A valid HuggingFace access token.

    Returns:
        OpenID Connect userinfo dict.
    """
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            HF_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()