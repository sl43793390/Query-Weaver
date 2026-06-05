"""Database adapter package — one module per backend."""
from src.database.adapters.base import BaseAdapter, SchemaInfo, QueryResult
from src.database.adapters.factory import get_adapter, supported_types

__all__ = ["BaseAdapter", "SchemaInfo", "QueryResult", "get_adapter", "supported_types"]
