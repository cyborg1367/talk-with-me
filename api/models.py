"""
api/models.py — Pydantic models for all API request and response payloads.
"""

from pydantic import BaseModel, Field


# ── Chat ──────────────────────────────────────────────────────────────────

class Message(BaseModel):
    """A single turn in the conversation history."""

    role:    str = Field(..., description="'user' or 'assistant'")
    content: str = Field(..., description="The message text")


class ChatRequest(BaseModel):
    """Incoming chat request sent by the frontend."""

    message: str = Field(..., min_length=1, max_length=4000)
    history: list[Message] = Field(default_factory=list)
    # Signed-in users pass conv_id so messages are persisted to SQLite.
    # Guests omit it — chat still works, nothing is saved.
    conv_id: int | None = Field(default=None, description="Active conversation id")


class ChatResponse(BaseModel):
    """Chat response returned to the frontend (non-streaming fallback)."""

    response: str


# ── Profile ───────────────────────────────────────────────────────────────

class ProfileResponse(BaseModel):
    name: str
    initials: str
    title: str
    tagline: str
    skills: list[str]
    linkedin_url: str
    github_url: str
    email: str
    status: str
    suggested_questions: list[str]


# ── Contact CTA ───────────────────────────────────────────────────────────

class ContactRequest(BaseModel):
    name:  str = Field(..., min_length=1, max_length=100)
    email: str = Field(..., min_length=5, max_length=200)
    notes: str = Field(default="", max_length=500)


class ContactResponse(BaseModel):
    success: bool
    message: str = "Thank you! Your message has been received."


# ── Conversation history ──────────────────────────────────────────────────

class ConversationOut(BaseModel):
    """A conversation summary shown in the history list."""

    id:         int
    title:      str
    started_at: str
    updated_at: str


class MessageOut(BaseModel):
    """A single persisted message returned when loading a conversation."""

    id:         int
    role:       str
    content:    str
    created_at: str


class NewConversationResponse(BaseModel):
    """Returned when the frontend creates a new conversation."""

    id:    int
    title: str