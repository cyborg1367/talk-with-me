"""
config.py — Centralised application settings.
"""

import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv(override=True)


@dataclass(frozen=True)
class Settings:
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    pushover_token: str = os.getenv("PUSHOVER_TOKEN", "")
    pushover_user: str  = os.getenv("PUSHOVER_USER", "")
    model: str          = "llama-3.3-70b-versatile"
    base_url: str       = "https://api.groq.com/openai/v1"
    timeout: int        = 60
    linkedin_pdf: str   = "profile/linkedin.pdf"
    summary_txt: str    = "profile/summary.txt"


settings = Settings()