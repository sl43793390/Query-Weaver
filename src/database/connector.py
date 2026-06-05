"""Connection profile + execution facade on top of `BaseAdapter`.

The UI / business code talks to this module; it owns lifecycle,
credential decryption, read-only enforcement, and history logging.
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, asdict
from typing import Optional

from src.core.crypto import decrypt
from src.core.logger import logger
from src.database.adapters import get_adapter
from src.database.adapters.base import BaseAdapter, QueryResult
from src.database.local_db import get_connection
from src.security.sql_guard import analyze


@dataclass
class ConnectionProfile:
    id: Optional[int]
    name: str
    db_type: str
    host: str = ""
    port: int = 0
    database: str = ""
    username: str = ""
    password: str = ""           # Plaintext — held only in memory
    options: dict | None = None
    read_only: bool = True

    def to_adapter_config(self) -> dict:
        return {
            "host": self.host,
            "port": self.port,
            "database": self.database,
            "username": self.username,
            "password": self.password,
            "options": self.options or {},
        }


# --------------------------------------------------------------------------- #
# CRUD
# --------------------------------------------------------------------------- #
def list_connections() -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, name, db_type, host, port, database, username, read_only "
        "FROM connections ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_connection_profile(conn_id: int) -> Optional[ConnectionProfile]:
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM connections WHERE id = ?", (conn_id,)
    ).fetchone()
    conn.close()
    if not row:
        return None
    return _row_to_profile(row)


def save_connection(profile: ConnectionProfile) -> int:
    """Insert or update; returns the row id."""
    from src.core.crypto import encrypt  # local import to avoid cycle on first import

    conn = get_connection()
    try:
        if profile.id:
            conn.execute(
                """UPDATE connections SET
                       name=?, db_type=?, host=?, port=?, database=?,
                       username=?, password_enc=?, options_json=?, read_only=?
                   WHERE id=?""",
                (
                    profile.name,
                    profile.db_type,
                    profile.host,
                    profile.port,
                    profile.database,
                    profile.username,
                    encrypt(profile.password),
                    json.dumps(profile.options or {}),
                    1 if profile.read_only else 0,
                    profile.id,
                ),
            )
            conn_id = profile.id
        else:
            cur = conn.execute(
                """INSERT INTO connections
                       (name, db_type, host, port, database, username,
                        password_enc, options_json, read_only)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    profile.name,
                    profile.db_type,
                    profile.host,
                    profile.port,
                    profile.database,
                    profile.username,
                    encrypt(profile.password),
                    json.dumps(profile.options or {}),
                    1 if profile.read_only else 0,
                ),
            )
            conn_id = cur.lastrowid
        conn.commit()
        return conn_id
    finally:
        conn.close()


def delete_connection(conn_id: int) -> None:
    conn = get_connection()
    conn.execute("DELETE FROM connections WHERE id = ?", (conn_id,))
    conn.commit()
    conn.close()


def _row_to_profile(row: sqlite3.Row) -> ConnectionProfile:
    return ConnectionProfile(
        id=row["id"],
        name=row["name"],
        db_type=row["db_type"],
        host=row["host"] or "",
        port=row["port"] or 0,
        database=row["database"] or "",
        username=row["username"] or "",
        password=decrypt(row["password_enc"] or ""),
        options=json.loads(row["options_json"] or "{}"),
        read_only=bool(row["read_only"]),
    )


# --------------------------------------------------------------------------- #
# Execution with safety + history
# --------------------------------------------------------------------------- #
def execute_on_connection(
    profile: ConnectionProfile,
    sql: str,
    *,
    force: bool = False,
) -> QueryResult:
    """Run `sql` on `profile`, with read-only + DML confirmation.

    `force=True` skips the guard (caller has already confirmed).
    Raises `PermissionError` if the guard blocks the statement.
    """
    report = analyze(sql, db_type=profile.db_type, read_only=profile.read_only)
    if not report.allowed and not force:
        raise PermissionError(report.reason or "Blocked by SQL guard")

    adapter: BaseAdapter = get_adapter(profile.db_type, profile.to_adapter_config())
    try:
        adapter.connect()
        result = adapter.execute(sql)
    except Exception as exc:
        logger.exception("Execution failed on connection {}", profile.name)
        _log_history(profile, sql, status="error", error=str(exc))
        raise
    else:
        _log_history(
            profile,
            sql,
            status="ok",
            rows=result.row_count,
            duration_ms=result.duration_ms,
        )
        return result
    finally:
        adapter.close()


def _log_history(
    profile: ConnectionProfile,
    sql: str,
    *,
    status: str,
    rows: int = 0,
    duration_ms: int = 0,
    error: str = "",
) -> None:
    conn = get_connection()
    conn.execute(
        "INSERT INTO query_history"
        "(connection_id, db_type, sql, rows, duration_ms, status, error)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        (profile.id, profile.db_type, sql, rows, duration_ms, status, error),
    )
    conn.commit()
    conn.close()


# --------------------------------------------------------------------------- #
# Convenience
# --------------------------------------------------------------------------- #
def test_connection(profile: ConnectionProfile) -> tuple[bool, str]:
    adapter = get_adapter(profile.db_type, profile.to_adapter_config())
    return adapter.test()


def asdict_safe(profile: ConnectionProfile) -> dict:
    d = asdict(profile)
    d.pop("password", None)
    return d
