"""Local SQLite store for Query-Weaver metadata.

This is the on-device database for:
    - saved remote connections (passwords encrypted via Fernet)
    - chat / message history
    - query history
    - saved SQL snippets / favorites
    - generic app settings (key/value)

It is intentionally simple — sqlite3 stdlib is enough; no ORM required.
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from config.settings import LOCAL_DB_PATH
from src.core.logger import logger

_SCHEMA = """
CREATE TABLE IF NOT EXISTS connections (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT    NOT NULL UNIQUE,
    db_type       TEXT    NOT NULL,
    host          TEXT,
    port          INTEGER,
    database      TEXT,
    username      TEXT,
    password_enc  TEXT,
    options_json  TEXT,
    read_only     INTEGER NOT NULL DEFAULT 1,
    created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS chats (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    connection_id INTEGER REFERENCES connections(id) ON DELETE CASCADE,
    title         TEXT    NOT NULL,
    created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS messages (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id       INTEGER NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
    role          TEXT    NOT NULL,         -- 'user' | 'assistant' | 'system'
    content       TEXT    NOT NULL,
    sql           TEXT,
    created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS query_history (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    connection_id INTEGER REFERENCES connections(id) ON DELETE SET NULL,
    db_type       TEXT    NOT NULL,
    sql           TEXT    NOT NULL,
    rows          INTEGER,
    duration_ms   INTEGER,
    status        TEXT    NOT NULL,         -- 'ok' | 'error'
    error         TEXT,
    created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS favorites (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT    NOT NULL,
    sql           TEXT    NOT NULL,
    tags          TEXT,
    created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS settings (
    key           TEXT PRIMARY KEY,
    value         TEXT
);

CREATE INDEX IF NOT EXISTS idx_messages_chat ON messages(chat_id);
CREATE INDEX IF NOT EXISTS idx_history_conn  ON query_history(connection_id);
"""


def _ensure_db() -> None:
    Path(LOCAL_DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(LOCAL_DB_PATH) as conn:
        conn.executescript(_SCHEMA)
        conn.commit()


# Initialise on import — cheap idempotent operation.
_ensure_db()


def get_connection() -> sqlite3.Connection:
    """Return a new sqlite3 connection with row access by name."""
    conn = sqlite3.connect(LOCAL_DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


@contextmanager
def transaction() -> Iterator[sqlite3.Connection]:
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def reset_database() -> None:  # pragma: no cover - destructive helper
    """Delete the local DB file. Used by Settings → "Reset". Caller must confirm."""
    try:
        Path(LOCAL_DB_PATH).unlink(missing_ok=True)
        _ensure_db()
        logger.warning("Local database reset at {}", LOCAL_DB_PATH)
    except OSError as exc:
        logger.error("Failed to reset database: {}", exc)


__all__ = ["get_connection", "transaction", "reset_database"]
