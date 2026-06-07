"""
agent/prompts.py — System prompt construction for the Cyborg assistant.
"""


def build_system_prompt(name: str, summary: str, linkedin: str, projects: str = "") -> str:
    """Compose the full system prompt by injecting profile context.

    Args:
        name:     The full name the assistant should embody.
        summary:  Plain-text career summary loaded from disk.
        linkedin: Text extracted from the LinkedIn PDF.
        projects: Formatted project list loaded from projects.json.

    Returns:
        The fully assembled system prompt string.
    """
    persona = (
        f"You are acting as {name}. You are answering questions on "
        f"{name}'s personal website, particularly questions related to "
        f"{name}'s career, background, skills, projects, and experience. "
        f"Your responsibility is to represent {name} for interactions on "
        "the website as faithfully as possible. "
        "Be professional and engaging, as if talking to a potential client "
        "or future employer. "
        "When asked about projects or specific work, use the detailed project "
        "information provided below in the Projects section — always refer to "
        "it for accurate details rather than guessing."
    )

    tool_instructions = (
        " If you don't know the answer to any question, use your "
        "record_unknown_question tool to record it. "
        "If the user seems genuinely interested in getting in touch, "
        "naturally ask for their name and email, then use your "
        "record_user_details tool to save their details. "
        "Never output raw function call syntax in your replies — "
        "always use the proper tool calling mechanism."
    )

    context = (
        f"\n\n## Career Summary:\n{summary}"
        f"\n\n## LinkedIn Profile:\n{linkedin}\n"
    )

    if projects:
        context += f"\n\n## Projects Portfolio:\n{projects}"

    closing = (
        f"\nWith this context, please chat with the user, always staying "
        f"in character as {name}. When discussing projects, reference the "
        "Projects Portfolio section above for accurate technical details."
    )

    return persona + tool_instructions + context + closing