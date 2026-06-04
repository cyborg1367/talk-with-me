"""
db/database.py — SQLite connection pool and schema initialisation.

The database file is stored at the path defined in config.py.
All tables are created on first startup via init_db().
"""

import logging
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from config import settings

logger = logging.getLogger(__name__)


def _connect() -> sqlite3.Connection:
    """Open a new SQLite connection with sensible defaults.

    - ``check_same_thread=False`` is required for FastAPI's async context.
    - ``isolation_level=None`` enables autocommit; we manage transactions
      explicitly with BEGIN / COMMIT / ROLLBACK where needed.
    - Row factory set to ``sqlite3.Row`` so columns are accessible by name.
    """
    conn = sqlite3.connect(
        settings.db_path,
        check_same_thread=False,
    )
    conn.row_factory = sqlite3.Row
    # Enable WAL mode for better concurrent read performance
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def get_db():
    """Context manager that yields a connection and closes it on exit.

    Usage::

        with get_db() as db:
            db.execute("SELECT ...")
    """
    conn = _connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── Schema ────────────────────────────────────────────────────────────────

_SCHEMA = """
-- One row per HuggingFace user that has ever signed in.
CREATE TABLE IF NOT EXISTS users (
    id          TEXT PRIMARY KEY,   -- HuggingFace user id  (e.g. "cyborgmass")
    username    TEXT NOT NULL,
    avatar_url  TEXT NOT NULL DEFAULT '',
    email       TEXT NOT NULL DEFAULT '',
    created_at  DATETIME NOT NULL DEFAULT (datetime('now'))
);

-- One conversation per chat session.
-- A new row is created each time a logged-in user opens a fresh chat.
CREATE TABLE IF NOT EXISTS conversations (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     TEXT    NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title       TEXT    NOT NULL DEFAULT 'New conversation',
    started_at  DATETIME NOT NULL DEFAULT (datetime('now')),
    updated_at  DATETIME NOT NULL DEFAULT (datetime('now'))
);

-- Individual messages within a conversation.
CREATE TABLE IF NOT EXISTS messages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    conv_id     INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role        TEXT    NOT NULL CHECK(role IN ('user', 'assistant')),
    content     TEXT    NOT NULL,
    created_at  DATETIME NOT NULL DEFAULT (datetime('now'))
);

-- Indices for the most common queries
CREATE INDEX IF NOT EXISTS idx_conv_user    ON conversations(user_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_msg_conv     ON messages(conv_id, created_at ASC);
"""


def init_db() -> None:
    """Create all tables and indices if they do not already exist.

    Called once at application startup from app.py's lifespan handler.
    Safe to call repeatedly — uses CREATE IF NOT EXISTS throughout.
    """
    # Ensure the parent directory exists (e.g. data/ folder)
    Path(settings.db_path).parent.mkdir(parents=True, exist_ok=True)

    with get_db() as db:
        db.executescript(_SCHEMA)

    logger.info("Database ready at %s", settings.db_path)