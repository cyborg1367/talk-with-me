"""
api/models.py — Pydantic models for all API request and response payloads.
"""

from pydantic import BaseModel, Field


class Message(BaseModel):
    role:    str = Field(..., description="'user' or 'assistant'")
    content: str = Field(..., description="The message text")


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    history: list[Message] = Field(default_factory=list)


class ChatResponse(BaseModel):
    response: str


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


class ContactRequest(BaseModel):
    name:  str = Field(..., min_length=1, max_length=100)
    email: str = Field(..., min_length=5, max_length=200)
    notes: str = Field(default="", max_length=500)


class ContactResponse(BaseModel):
    success: bool
    message: str = "Thank you! Your message has been received."