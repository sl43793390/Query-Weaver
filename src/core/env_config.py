"""Resolve configuration values with this priority:

    1. Process environment variable   (e.g. `OPENAI_API_KEY`)
    2. Project-root `.env` file        (loaded via python-dotenv)
    3. Caller-supplied default

This lets operators ship credentials in env vars or a `.env` file at
deployment time, while still allowing the in-app settings dialog to
override them for one user.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Optional

from dotenv import dotenv_values

# The `.env` file is expected at the project root (one level above `src/`).
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_ENV_FILE = _PROJECT_ROOT / ".env"


@lru_cache(maxsize=1)
def _env_file_map() -> dict[str, str]:
    """Load the `.env` file once and cache the result. Missing files
    yield an empty dict, which is fine — env vars still win."""
    if not _ENV_FILE.is_file():
        return {}
    return {k: v for k, v in dotenv_values(_ENV_FILE).items() if v is not None}


def reload() -> None:
    """Drop the cached `.env` contents so a follow-up `resolve()` re-reads
    the file. Useful after writing a new `.env` from a settings dialog."""
    _env_file_map.cache_clear()


def resolve(
    env_var: str,
    default: Optional[str] = None,
    *,
    env_aliases: Optional[list[str]] = None,
) -> Optional[str]:
    """Return the first non-empty value among:

    - `os.environ[env_var]`
    - any of `env_aliases` in the environment
    - `os.environ[env_var]` from the `.env` file
    - any of `env_aliases` from the `.env` file
    - `default`
    """
    keys = [env_var] + list(env_aliases or [])
    env = _env_file_map()
    for k in keys:
        v = os.environ.get(k)
        if v:
            return v
    for k in keys:
        v = env.get(k)
        if v:
            return v
    return default


def source_of(env_var: str, *, env_aliases: Optional[list[str]] = None) -> str:
    """Return a human-readable label describing where `resolve()` would
    pick up `env_var`. Useful for tooltips / debug info."""
    keys = [env_var] + list(env_aliases or [])
    for k in keys:
        if os.environ.get(k):
            return f"env: {k}"
    env = _env_file_map()
    for k in keys:
        if env.get(k):
            return f".env: {k}"
    return "default"


__all__ = ["resolve", "source_of", "reload", "_ENV_FILE"]
