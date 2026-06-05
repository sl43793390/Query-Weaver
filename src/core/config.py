"""Lightweight key/value settings store backed by SQLite.

Application settings (LLM provider, model, theme, etc.) live in the
`settings(key TEXT PRIMARY KEY, value TEXT)` table. Encrypted secrets
go through `src.core.crypto` first.
"""
from __future__ import annotations

import json
from typing import Any

from src.database.local_db import get_connection
from src.core.crypto import encrypt, decrypt


def _row_to_value(row) -> str | None:
    return row["value"] if row else None


def get_value(key: str, default: str | None = None) -> str | None:
    conn = get_connection()
    cur = conn.execute("SELECT value FROM settings WHERE key = ?", (key,))
    val = _row_to_value(cur.fetchone())
    conn.close()
    return val if val is not None else default


def set_value(key: str, value: str) -> None:
    conn = get_connection()
    conn.execute(
        "INSERT INTO settings(key, value) VALUES(?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )
    conn.commit()
    conn.close()


def get_json(key: str, default: Any = None) -> Any:
    raw = get_value(key)
    if raw is None:
        return default
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return default


def set_json(key: str, value: Any) -> None:
    set_value(key, json.dumps(value, ensure_ascii=False))


# ---- Encrypted secret helpers ----
def get_secret(key: str) -> str:
    return decrypt(get_value(key, "") or "")


def set_secret(key: str, plaintext: str) -> None:
    set_value(key, encrypt(plaintext))


__all__ = [
    "get_value",
    "set_value",
    "get_json",
    "set_json",
    "get_secret",
    "set_secret",
]
