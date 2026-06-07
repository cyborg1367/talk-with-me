"""
profile_meta.py — Display metadata for the profile card in the chat UI.

This is the single file to edit when updating the sidebar: name, title,
skills, social links, and suggested questions.
No other module needs to change.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ProfileMeta:
    """Immutable display data rendered in the sidebar profile card.

    Attributes:
        name:                 Full name shown in the card header and page title.
        initials:             Two-letter abbreviation used in the avatar circle.
        title:                Professional title / current role.
        tagline:              One-line description shown under the title.
        skills:               Ordered list of technology / skill pill labels.
        linkedin_url:         Full LinkedIn URL — leave empty to hide the button.
        github_url:           Full GitHub URL — leave empty to hide the button.
        email:                Contact address — leave empty to hide the button.
        status:               Short availability label shown in the green badge.
        suggested_questions:  Clickable chips shown below the greeting.
                              Customise these to reflect the most common things
                              visitors ask. Max 4 recommended.
    """

    name: str         = "Masoud Ahangary"
    initials: str     = "MA"
    title: str        = "AI Engineer & Developer"
    tagline: str      = "Building intelligent systems with LLMs & Python"
    skills: list[str] = field(default_factory=lambda: [
        "Python", "LLMs", "AI Agents", "FastAPI", "LangChain", "OpenAI",
    ])
    linkedin_url: str = "https://linkedin.com/in/masoud-ahangary"
    github_url: str   = "https://github.com/cyborg1367"
    email: str        = ""   # e.g. "masoud@example.com"
    status: str       = "Open to opportunities"
    suggested_questions: list[str] = field(default_factory=lambda: [
        "What's your work experience?",
        "What technologies do you specialise in?",
        "Are you open to new opportunities?",
        "Tell me about your recent projects",
    ])


# Singleton imported by the UI layer.
profile_meta = ProfileMeta()