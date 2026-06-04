"""
api/models.py — Pydantic models for all API request and response payloads.
"""

from pydantic import BaseModel, Field


class Message(BaseModel):
    """A single turn in the conversation history."""

    role: str = Field(..., description="'user' or 'assistant'")
    content: str = Field(..., description="The message text")


class ChatRequest(BaseModel):
    """Incoming chat request sent by the frontend."""

    message: str = Field(..., min_length=1, max_length=4000, description="The user's message")
    history: list[Message] = Field(
        default_factory=list,
        description="All previous turns, excluding the current message",
    )


class ChatResponse(BaseModel):
    """Chat response returned to the frontend."""

    response: str = Field(..., description="The assistant's reply")


class ProfileResponse(BaseModel):
    """Structured profile data rendered in the frontend sidebar."""

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


class ContactRequest(BaseModel):
    """Visitor contact details submitted via the in-chat CTA."""

    name:  str = Field(..., min_length=1, max_length=100,  description="Visitor's name")
    email: str = Field(..., min_length=5, max_length=200,  description="Visitor's email address")
    notes: str = Field(default="", max_length=500, description="Conversation context snippet")


class ContactResponse(BaseModel):
    """Response returned after recording a visitor's contact details."""

    success: bool
    message: str = "Thank you! Your message has been received."