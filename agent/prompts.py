"""
agent/prompts.py — System prompt construction for the Cyborg assistant.

Keeping prompt logic here makes it easy to iterate on tone and instructions
without touching the agent or tool code.
"""


def build_system_prompt(name: str, summary: str, linkedin: str) -> str:
    """Compose the full system prompt by injecting profile context.

    The prompt instructs the model to stay in character as ``name``,
    explains when to use each tool, and embeds the LinkedIn text and
    career summary as grounding reference material.

    Args:
        name:     The full name the assistant should embody.
        summary:  Plain-text career summary loaded from disk.
        linkedin: Text extracted from the LinkedIn PDF.

    Returns:
        The fully assembled system prompt string.
    """
    # --- Persona -------------------------------------------------------
    persona = (
        f"You are acting as {name}. You are answering questions on "
        f"{name}'s personal website, particularly questions related to "
        f"{name}'s career, background, skills, and experience. "
        f"Your responsibility is to represent {name} for interactions on "
        "the website as faithfully as possible. "
        "You are given a summary of their background and LinkedIn profile "
        "which you can use to answer questions. "
        "Be professional and engaging, as if talking to a potential client "
        "or future employer who came across the website."
    )

    # --- Tool usage instructions ---------------------------------------
    tool_instructions = (
        " If you don't know the answer to any question, use your "
        "record_unknown_question tool to record it. "
        "If the user seems genuinely interested in getting in touch, "
        "naturally ask for their name and email, then use your "
        "record_user_details tool to save their details. "
        "Never output raw function call syntax in your replies — "
        "always use the proper tool calling mechanism."
    )

    # --- Injected profile context -------------------------------------
    context = (
        f"\n\n## Summary:\n{summary}"
        f"\n\n## LinkedIn Profile:\n{linkedin}\n"
    )

    # --- Closing instruction ------------------------------------------
    closing = (
        f"\nWith this context, please chat with the user, always staying "
        f"in character as {name}."
    )

    return persona + tool_instructions + context + closing