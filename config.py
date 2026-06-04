"""
config.py — Centralised application settings.

All environment variables and tuneable constants live here so that no other
module needs to call ``os.getenv()`` directly. Import the ``settings``
singleton instead:

    from config import settings
"""

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv(override=True)

# HuggingFace injects SPACE_HOST as just the hostname, e.g.
# "cyborgmass-talk-with-me.hf.space". Prepend https:// if needed.
_raw_host = os.getenv("SPACE_HOST", "")
if _raw_host and not _raw_host.startswith("http"):
    _space_host = f"https://{_raw_host}"
elif _raw_host:
    _space_host = _raw_host
else:
    _space_host = "http://localhost:8000"


@dataclass(frozen=True)
class Settings:
    """Immutable configuration loaded from environment variables.

    Attributes:
        openai_api_key:    API key forwarded to OpenRouter.
        pushover_token:    Pushover application token.
        pushover_user:     Pushover user/group key.
        model:             LLM model identifier passed to OpenRouter.
        base_url:          OpenRouter-compatible OpenAI base URL.
        timeout:           HTTP timeout in seconds for LLM requests.
        linkedin_pdf:      Filesystem path to the LinkedIn profile PDF.
        summary_txt:       Filesystem path to the plain-text career summary.
        db_path:           Filesystem path to the SQLite database file.
        hf_oauth_client_id:     HuggingFace OAuth client id (set by HF automatically).
        hf_oauth_client_secret: HuggingFace OAuth client secret (set by HF automatically).
        hf_space_host:     Public URL of the HuggingFace Space (for OAuth redirect).
        session_secret:    Secret key used to sign session cookies.
    """

    openai_api_key: str    = os.getenv("OPENAI_API_KEY", "")
    pushover_token: str    = os.getenv("PUSHOVER_TOKEN", "")
    pushover_user: str     = os.getenv("PUSHOVER_USER", "")
    model: str             = "openrouter/free"
    base_url: str          = "https://openrouter.ai/api/v1"
    timeout: int           = 60
    linkedin_pdf: str      = "profile/linkedin.pdf"
    summary_txt: str       = "profile/summary.txt"
    db_path: str           = os.getenv("DB_PATH", "data/chat.db")
    session_secret: str    = os.getenv("SESSION_SECRET", "change-me-in-production")


# Singleton imported by all other modules — never instantiate Settings directly.
settings = Settings()