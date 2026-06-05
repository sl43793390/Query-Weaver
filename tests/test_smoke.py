"""Smoke tests — run with `python tests/test_smoke.py`.

No external services required; exercises pure logic (crypto, SQL guard,
SQLite store, helpers, prompts, config).
"""
from __future__ import annotations

import os
import sys

# Add project root to sys.path so `src` and `config` are importable.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def test_crypto_roundtrip() -> None:
    from src.core.crypto import encrypt, decrypt
    token = encrypt("hello-world")
    assert decrypt(token) == "hello-world"
    assert decrypt("") == ""
    print("[OK] crypto round-trip")


def test_sql_guard() -> None:
    from src.security.sql_guard import analyze
    r = analyze("SELECT 1", db_type="mysql", read_only=True)
    assert r.allowed
    r = analyze("DROP TABLE users", db_type="mysql", read_only=True)
    assert not r.allowed
    r = analyze("DELETE FROM users", db_type="mysql", read_only=True)
    assert not r.allowed
    r = analyze("DELETE FROM users WHERE id=1", db_type="mysql", read_only=False)
    assert r.allowed
    r = analyze("SELECT 1; DROP TABLE x", db_type="mysql", read_only=True)
    assert not r.allowed
    print("[OK] sql guard")


def test_helpers() -> None:
    from src.utils.helpers import extract_code_blocks, first_code_block
    txt = "Here:\n```sql\nSELECT * FROM t\n```\nDone."
    assert "SELECT" in first_code_block(txt)
    assert len(extract_code_blocks(txt)) == 1
    print("[OK] helpers")


def test_prompts() -> None:
    from config.prompts import system_prompt_for
    assert "MYSQL" in system_prompt_for("mysql").upper()
    assert "MONGODB" in system_prompt_for("mongodb").upper()
    assert "REDIS" in system_prompt_for("redis").upper()
    print("[OK] prompts")


def test_local_db() -> None:
    from src.database.local_db import get_connection
    from src.database.connector import save_connection, list_connections, get_connection_profile, delete_connection
    from src.database.connector import ConnectionProfile

    profile = ConnectionProfile(
        id=None, name="__smoke__", db_type="mysql",
        host="127.0.0.1", port=3306, database="x",
        username="u", password="p", options={}, read_only=True,
    )
    cid = save_connection(profile)
    assert cid > 0
    rows = list_connections()
    assert any(r["id"] == cid for r in rows)
    loaded = get_connection_profile(cid)
    assert loaded is not None
    assert loaded.password == "p"   # round-trip encryption
    delete_connection(cid)
    assert get_connection_profile(cid) is None
    print("[OK] local db + connector")


def test_adapter_factory() -> None:
    from src.database.adapters import get_adapter, supported_types
    types = supported_types()
    assert {"mysql", "postgresql", "oracle", "mongodb", "redis"} <= set(types)
    a = get_adapter("mysql", {"host": "x", "port": 3306, "username": "u", "password": "p", "database": "d"})
    assert a.db_type == "mysql"
    print("[OK] adapter factory")


def test_settings_kv() -> None:
    from src.core.config import set_value, get_value, set_secret, get_secret
    set_value("smoke.key", "v1")
    assert get_value("smoke.key") == "v1"
    set_secret("smoke.secret", "super-secret")
    assert get_secret("smoke.secret") == "super-secret"
    print("[OK] settings kv")


if __name__ == "__main__":
    test_crypto_roundtrip()
    test_sql_guard()
    test_helpers()
    test_prompts()
    test_local_db()
    test_adapter_factory()
    test_settings_kv()
    print("\nAll smoke tests passed.")
