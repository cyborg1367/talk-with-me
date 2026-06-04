"""
notifications.py — Thin wrapper around the Pushover push-notification API.

Keeps all third-party notification logic in one place so it can be swapped
out (e.g. for email or SMS) without touching the rest of the codebase.
"""

import requests

from config import settings


def push(text: str) -> None:
    """Send a push notification to the owner's device via Pushover.

    Args:
        text: The message body to deliver to the device.
    """
    requests.post(
        url="https://api.pushover.net/1/messages.json",
        data={
            "token":   settings.pushover_token,
            "user":    settings.pushover_user,
            "message": text,
        },
    )