"""
db/queries.py — All SQL query helpers.

Each function takes a ``sqlite3.Connection`` as its first argument so the
caller controls the transaction boundary. Functions are pure data — no HTTP,
no business logic.
"""

import sqlite3
from dataclasses import dataclass
from datetime import datetime


# ── Data classes ──────────────────────────────────────────────────────────

@dataclass
class User:
    id:         str
    username:   str
    avatar_url: str
    email:      str
    created_at: str


@dataclass
class Conversation:
    id:         int
    user_id:    str
    title:      str
    started_at: str
    updated_at: str


@dataclass
class Message:
    id:         int
    conv_id:    int
    role:       str
    content:    str
    created_at: str


# ── Users ─────────────────────────────────────────────────────────────────

def upsert_user(
    db: sqlite3.Connection,
    *,
    id: str,
    username: str,
    avatar_url: str = "",
    email: str = "",
) -> User:
    """Insert a new user or update their profile if they already exist.

    Called every time a user completes the OAuth login flow so their
    username and avatar stay in sync with HuggingFace.
    """
    db.execute(
        """
        INSERT INTO users (id, username, avatar_url, email)
        VALUES (:id, :username, :avatar_url, :email)
        ON CONFLICT(id) DO UPDATE SET
            username   = excluded.username,
            avatar_url = excluded.avatar_url,
            email      = excluded.email
        """,
        {"id": id, "username": username, "avatar_url": avatar_url, "email": email},
    )
    return get_user(db, id=id)


def get_user(db: sqlite3.Connection, *, id: str) -> User | None:
    """Fetch a single user by their HuggingFace id."""
    row = db.execute(
        "SELECT id, username, avatar_url, email, created_at FROM users WHERE id = ?",
        (id,),
    ).fetchone()
    return User(**dict(row)) if row else None


# ── Conversations ─────────────────────────────────────────────────────────

def create_conversation(
    db: sqlite3.Connection,
    *,
    user_id: str,
    title: str = "New conversation",
) -> Conversation:
    """Create a new conversation for a user and return it."""
    cursor = db.execute(
        "INSERT INTO conversations (user_id, title) VALUES (?, ?)",
        (user_id, title),
    )
    return get_conversation(db, id=cursor.lastrowid)


def get_conversation(db: sqlite3.Connection, *, id: int) -> Conversation | None:
    """Fetch a single conversation by id."""
    row = db.execute(
        "SELECT id, user_id, title, started_at, updated_at FROM conversations WHERE id = ?",
        (id,),
    ).fetchone()
    return Conversation(**dict(row)) if row else None


def get_user_conversations(
    db: sqlite3.Connection,
    *,
    user_id: str,
    limit: int = 20,
) -> list[Conversation]:
    """Return a user's most recent conversations, newest first."""
    rows = db.execute(
        """
        SELECT id, user_id, title, started_at, updated_at
        FROM   conversations
        WHERE  user_id = ?
        ORDER  BY updated_at DESC
        LIMIT  ?
        """,
        (user_id, limit),
    ).fetchall()
    return [Conversation(**dict(r)) for r in rows]


def update_conversation_title(
    db: sqlite3.Connection,
    *,
    conv_id: int,
    title: str,
) -> None:
    """Update the conversation title (set from the first user message)."""
    db.execute(
        "UPDATE conversations SET title = ?, updated_at = datetime('now') WHERE id = ?",
        (title, conv_id),
    )


def touch_conversation(db: sqlite3.Connection, *, conv_id: int) -> None:
    """Bump updated_at to now so the conversation floats to the top of the list."""
    db.execute(
        "UPDATE conversations SET updated_at = datetime('now') WHERE id = ?",
        (conv_id,),
    )


# ── Messages ──────────────────────────────────────────────────────────────

def add_message(
    db: sqlite3.Connection,
    *,
    conv_id: int,
    role: str,
    content: str,
) -> Message:
    """Insert a single message and return it."""
    cursor = db.execute(
        "INSERT INTO messages (conv_id, role, content) VALUES (?, ?, ?)",
        (conv_id, role, content),
    )
    row = db.execute(
        "SELECT id, conv_id, role, content, created_at FROM messages WHERE id = ?",
        (cursor.lastrowid,),
    ).fetchone()
    return Message(**dict(row))


def get_conversation_messages(
    db: sqlite3.Connection,
    *,
    conv_id: int,
) -> list[Message]:
    """Return all messages for a conversation in chronological order."""
    rows = db.execute(
        """
        SELECT id, conv_id, role, content, created_at
        FROM   messages
        WHERE  conv_id = ?
        ORDER  BY created_at ASC
        """,
        (conv_id,),
    ).fetchall()
    return [Message(**dict(r)) for r in rows]


def get_conversation_history(
    db: sqlite3.Connection,
    *,
    conv_id: int,
) -> list[dict]:
    """Return messages as plain dicts ready to be passed to the LLM.

    Returns:
        List of ``{"role": "user"|"assistant", "content": "..."}`` dicts.
    """
    return [
        {"role": m.role, "content": m.content}
        for m in get_conversation_messages(db, conv_id=conv_id)
    ]