"""Abstract base class and shared dataclasses for all DB adapters."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional

import pandas as pd


@dataclass
class QueryResult:
    """Normalised result returned by every adapter."""
    columns: list[str] = field(default_factory=list)
    rows: list[list[Any]] = field(default_factory=list)
    row_count: int = 0
    duration_ms: int = 0
    message: str = ""           # For non-SELECT commands, e.g. "3 rows affected"
    is_dml: bool = False        # True if the statement mutated data
    affected_rows: int = 0

    def to_dataframe(self) -> pd.DataFrame:
        return pd.DataFrame(self.rows, columns=self.columns)

    def to_dict(self) -> dict:
        return {
            "columns": self.columns,
            "rows": self.rows,
            "row_count": self.row_count,
            "duration_ms": self.duration_ms,
            "message": self.message,
            "is_dml": self.is_dml,
            "affected_rows": self.affected_rows,
        }


@dataclass
class ColumnInfo:
    name: str
    data_type: str
    nullable: bool = True
    comment: str = ""


@dataclass
class TableInfo:
    name: str
    schema: str = ""
    columns: list[ColumnInfo] = field(default_factory=list)
    comment: str = ""


@dataclass
class DatabaseInfo:
    """A logical database / schema / namespace. Rendered as a top-level
    entry in the schema tree (e.g. one MySQL database, one Postgres
    schema, one Oracle user, or one Mongo database)."""
    name: str
    tables: list[TableInfo] = field(default_factory=list)


@dataclass
class SchemaInfo:
    """Holds the schema of one or more databases under a single connection."""
    default_database: str = ""          # the database configured in the connection
    databases: list[DatabaseInfo] = field(default_factory=list)

    def to_compact_text(self, max_tables: int = 50) -> str:
        """Render a compact, token-friendly representation for LLM prompts."""
        lines: list[str] = []
        for db in self.databases:
            lines.append(f"Database: {db.name}")
            for t in db.tables[:max_tables]:
                cols = ", ".join(f"{c.name} {c.data_type}" for c in t.columns)
                lines.append(f"- {t.name}({cols})")
            if len(db.tables) > max_tables:
                lines.append(f"... and {len(db.tables) - max_tables} more tables")
            lines.append("")
        if not lines:
            return "(no schema available)"
        return "\n".join(lines).rstrip()


class BaseAdapter(ABC):
    """Common interface for every database adapter.

    Concrete subclasses must implement `connect`, `close`, `test`, `execute`,
    `fetch_schema`. Read-only enforcement happens at the SQL-guard level
    (see `src.security.sql_guard`).
    """

    db_type: str = "base"

    def __init__(self, config: dict):
        self.config = config or {}
        self._conn = None

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #
    @abstractmethod
    def connect(self) -> None: ...

    @abstractmethod
    def close(self) -> None: ...

    def test(self) -> tuple[bool, str]:
        """Default implementation runs `SELECT 1` / equivalent. Override if needed."""
        try:
            self.connect()
            self.execute("SELECT 1")
            return True, "Connection OK"
        except Exception as exc:
            return False, str(exc)
        finally:
            self.close()

    # ------------------------------------------------------------------ #
    # Execution
    # ------------------------------------------------------------------ #
    @abstractmethod
    def execute(self, sql: str, params: Optional[dict] = None) -> QueryResult: ...

    @abstractmethod
    def list_databases(self) -> list[str]:
        """Return the names of all databases / schemas / namespaces the
        current user can see on this connection. The configured default
        database should be in this list if visible."""

    @abstractmethod
    def fetch_schema(self) -> SchemaInfo:
        """Fetch a `SchemaInfo` for every database the user can see."""

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    @property
    def is_connected(self) -> bool:
        return self._conn is not None

    @staticmethod
    def normalize_sql_for_readonly(sql: str) -> str:
        """Hook: subclasses can strip driver-specific options that confuse
        a read-only transaction (e.g. MySQL `LOCK TABLES`). Default no-op."""
        return sql
