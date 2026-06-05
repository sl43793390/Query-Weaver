"""Schema discovery and in-memory cache, used by the LLM and the tree view."""
from __future__ import annotations

from src.core.logger import logger
from src.database.adapters import get_adapter
from src.database.adapters.base import SchemaInfo
from src.database.connector import ConnectionProfile


_CACHE: dict[int, SchemaInfo] = {}


def get_schema(profile: ConnectionProfile, *, refresh: bool = False) -> SchemaInfo:
    """Return the schema for `profile`, caching by profile id."""
    if not refresh and profile.id in _CACHE:
        return _CACHE[profile.id]

    adapter = get_adapter(profile.db_type, profile.to_adapter_config())
    try:
        adapter.connect()
        info = adapter.fetch_schema()
    except Exception:
        logger.exception("Failed to fetch schema for {}", profile.name)
        info = SchemaInfo(default_database=profile.database or "")
    finally:
        adapter.close()

    _CACHE[profile.id or -1] = info
    return info


def invalidate(profile_id: int | None) -> None:
    if profile_id is None:
        _CACHE.clear()
    else:
        _CACHE.pop(profile_id, None)


__all__ = ["get_schema", "invalidate"]
