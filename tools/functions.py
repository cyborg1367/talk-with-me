"""
tools/functions.py — Python callables that back each LLM tool.

These functions are invoked by the agent when the model emits a tool-call.
Each one triggers a Pushover notification so the owner is alerted in real time.

To add a new tool:
  1. Define the function here and add it to ``TOOL_REGISTRY``.
  2. Add its JSON schema to ``schemas.py``.
  3. Add it to ``TOOLS`` in ``__init__.py``.
"""

from notifications import push


def record_user_details(
    email: str,
    name: str = "Not provided",
    notes: str = "Not provided",
) -> dict[str, str]:
    """Record a visitor's contact details and notify the owner.

    Called by the LLM when a user expresses interest in getting in touch
    and supplies an email address.

    Args:
        email: The visitor's email address (required).
        name:  The visitor's name, if they provided it.
        notes: Contextual notes from the conversation.

    Returns:
        ``{"recorded": "ok"}`` on success.
    """
    push(f"Recording {name} with email {email} and notes {notes}")
    return {"recorded": "ok"}


def record_unknown_question(question: str) -> dict[str, str]:
    """Record a question the assistant was unable to answer.

    The LLM must call this whenever it cannot answer a question so the owner
    can identify gaps in the profile / summary context files.

    Args:
        question: The question that could not be answered.

    Returns:
        ``{"recorded": "ok"}`` on success.
    """
    push(f"Recording unknown question: {question}")
    return {"recorded": "ok"}


# Dispatch table — maps each tool name to its Python callable.
# The agent uses this instead of globals() for safe, explicit lookups.
TOOL_REGISTRY: dict[str, callable] = {
    record_user_details.__name__:    record_user_details,
    record_unknown_question.__name__: record_unknown_question,
}