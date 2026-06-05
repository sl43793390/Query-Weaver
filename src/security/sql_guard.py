"""SQL safety guard.

Uses `sqlparse` to inspect a statement and decide whether it should be
allowed in the current context.

Rules
-----
1. Multi-statement inputs are refused (we only run one statement at a time).
2. `read_only=True` blocks anything that is not SELECT / SHOW / EXPLAIN / DESC.
3. `DELETE` / `UPDATE` without a `WHERE` clause is always flagged.
4. `DROP`, `TRUNCATE`, `ALTER`, `GRANT`, `REVOKE` are always flagged.
5. For NoSQL adapters the guard is a no-op (we trust the LLM + explicit UI).
"""
from __future__ import annotations

from dataclasses import dataclass

import sqlparse
from sqlparse.sql import Statement
from sqlparse.tokens import Keyword, DML, DDL

_NOSQL = {"mongodb", "redis"}

_ALLOWED_READ = {"SELECT", "SHOW", "EXPLAIN", "DESCRIBE", "DESC", "WITH"}
_BLOCKED_ALWAYS = {"DROP", "TRUNCATE", "ALTER", "GRANT", "REVOKE", "RENAME"}


@dataclass
class GuardReport:
    allowed: bool
    is_dml: bool
    statement_type: str
    reason: str = ""

    def __str__(self) -> str:       # pragma: no cover
        return f"[{'OK' if self.allowed else 'BLOCKED'}] {self.statement_type}: {self.reason}"


def analyze(sql: str, *, db_type: str, read_only: bool = True) -> GuardReport:
    """Classify `sql` and decide whether it can be executed."""
    db_type = (db_type or "").lower()
    if db_type in _NOSQL:
        # Trust the LLM envelope; the UI still asks for DML confirmation.
        return GuardReport(allowed=True, is_dml=True, statement_type="NOSQL")

    if not sql or not sql.strip():
        return GuardReport(False, False, "EMPTY", "Empty statement")

    statements: list[Statement] = [s for s in sqlparse.parse(sql) if s.tokens]
    if not statements:
        return GuardReport(False, False, "EMPTY", "No parseable statement")
    if len(statements) > 1:
        return GuardReport(
            False, False, "MULTI", "Multiple statements are not allowed"
        )

    stmt = statements[0]
    stmt_type = (stmt.get_type() or "").upper()
    head = stmt_type or _first_keyword(stmt)

    if head in _BLOCKED_ALWAYS:
        return GuardReport(
            False, True, head, f"{head} is blocked by the SQL guard"
        )

    if read_only and head not in _ALLOWED_READ:
        return GuardReport(
            False, True, head,
            f"Read-only mode is on; {head} is not permitted",
        )

    if head in {"DELETE", "UPDATE"} and not _has_where(stmt):
        return GuardReport(
            False, True, head,
            f"{head} without a WHERE clause is blocked",
        )

    is_dml = head in {"INSERT", "UPDATE", "DELETE", "REPLACE", "MERGE"}
    return GuardReport(True, is_dml, head or "UNKNOWN")


# ----------------------------------------------------------------------- #
# Helpers
# ----------------------------------------------------------------------- #
def _first_keyword(stmt: Statement) -> str:
    for tok in stmt.flatten():
        if tok.ttype in (Keyword, DML, DDL):
            return tok.value.upper()
        if tok.is_word:
            return tok.value.upper()
    return ""


def _has_where(stmt: Statement) -> bool:
    text = "".join(str(t) for t in stmt.flatten()).upper()
    return " WHERE " in f" {text} "


__all__ = ["analyze", "GuardReport"]
