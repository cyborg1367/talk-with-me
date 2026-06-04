"""
config.py — Centralised application settings.

All environment variables and tune-able constants live here so that no other
module needs to call ``os.getenv()`` directly. Import the ``settings``
singleton instead:

    from config import settings
"""

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv(override=True)


@dataclass(frozen=True)
class Settings:
    """Immutable configuration loaded from environment variables.

    Attributes:
        openai_api_key: API key forwarded to OpenRouter.
        pushover_token: Pushover application token.
        pushover_user:  Pushover user/group key.
        model:          LLM model identifier passed to OpenRouter.
        base_url:       OpenRouter-compatible OpenAI base URL.
        timeout:        HTTP timeout in seconds for LLM requests.
        linkedin_pdf:   Filesystem path to the LinkedIn profile PDF.
        summary_txt:    Filesystem path to the plain-text career summary.
    """

    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    pushover_token: str = os.getenv("PUSHOVER_TOKEN", "")
    pushover_user: str  = os.getenv("PUSHOVER_USER", "")
    model: str          = "openrouter/free"
    base_url: str       = "https://openrouter.ai/api/v1"
    timeout: int        = 60
    linkedin_pdf: str   = "profile/linkedin.pdf"
    summary_txt: str    = "profile/summary.txt"


# Singleton imported by all other modules — never instantiate Settings directly.
settings = Settings()