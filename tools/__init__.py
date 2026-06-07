"""
tools/__init__.py — Public interface for the tools package.

Exposes ``TOOLS``, the list passed to every chat completion request,
so callers only need:

    from tools import TOOLS
"""

from tools.schemas import (
    record_unknown_question_schema,
    record_user_details_schema,
    search_projects_schema,
)

# Bundled tool list in the format expected by the OpenAI chat completions API.
TOOLS: list[dict] = [
    {"type": "function", "function": record_user_details_schema},
    {"type": "function", "function": record_unknown_question_schema},
    {"type": "function", "function": search_projects_schema},
]