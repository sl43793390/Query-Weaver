"""SQL execution helpers used by the UI layer.

The UI calls into `connector.execute_on_connection` for actual work;
this module is reserved for higher-level utilities (e.g. transaction mode,
pagination) that may be added later.
"""
from __future__ import annotations

from src.database.adapters.base import QueryResult
from src.database.connector import (
    ConnectionProfile,
    execute_on_connection,
)

__all__ = ["ConnectionProfile", "QueryResult", "execute_on_connection"]
