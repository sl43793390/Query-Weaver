"""Factory that returns a properly configured adapter instance."""
from __future__ import annotations

from typing import Mapping

from src.database.adapters.base import BaseAdapter
from src.database.adapters.mysql_adapter import MySQLAdapter
from src.database.adapters.postgresql_adapter import PostgreSQLAdapter
from src.database.adapters.oracle_adapter import OracleAdapter
from src.database.adapters.mongodb_adapter import MongoDBAdapter
from src.database.adapters.redis_adapter import RedisAdapter

_REGISTRY: dict[str, type[BaseAdapter]] = {
    "mysql": MySQLAdapter,
    "postgresql": PostgreSQLAdapter,
    "oracle": OracleAdapter,
    "mongodb": MongoDBAdapter,
    "redis": RedisAdapter,
}


def get_adapter(db_type: str, config: Mapping) -> BaseAdapter:
    """Instantiate an adapter for the requested database type.

    Raises `ValueError` for unsupported types. The returned adapter is
    NOT yet connected; call `.connect()` or `.test()`.
    """
    key = (db_type or "").lower()
    cls = _REGISTRY.get(key)
    if cls is None:
        raise ValueError(f"Unsupported database type: {db_type!r}")
    return cls(dict(config))


def supported_types() -> list[str]:
    return list(_REGISTRY.keys())


__all__ = ["get_adapter", "supported_types"]
