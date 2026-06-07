"""
tools/__init__.py — Public interface for the tools package.

search_projects is intentionally NOT in this list — project information
is embedded directly in the system prompt to avoid tool_use_failed errors
on models that struggle with text-based function call formats.
"""

from tools.schemas import record_unknown_question_schema, record_user_details_schema

TOOLS: list[dict] = [
    {"type": "function", "function": record_user_details_schema},
    {"type": "function", "function": record_unknown_question_schema},
]