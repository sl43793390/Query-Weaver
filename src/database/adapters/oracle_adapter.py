"""Oracle adapter using `oracledb` (the modern, officially supported driver).

`oracledb` is the successor to `cx_Oracle` and works in two modes:
  - "thin" (default): pure-Python, no Oracle Instant Client required.
  - "thick": optional, requires Instant Client. Enable via
             `oracledb.init_oracle_client()` if you need legacy features.

See: https://python-oracledb.readthedocs.io/
"""
from __future__ import annotations

import time

from src.database.adapters.base import (
    BaseAdapter,
    ColumnInfo,
    DatabaseInfo,
    QueryResult,
    SchemaInfo,
    TableInfo,
)
from src.core.logger import logger

_DEFAULT_PORT = 1521


class OracleAdapter(BaseAdapter):
    db_type = "oracle"

    def _import_driver(self):
        try:
            import oracledb  # type: ignore
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "oracledb is not installed. Run `pip install oracledb`."
            ) from exc
        return oracledb

    def connect(self) -> None:
        oracledb = self._import_driver()

        host = self.config.get("host", "127.0.0.1")
        port = int(self.config.get("port") or _DEFAULT_PORT)
        service_name = self.config.get("database")  # service name in the dsn

        # Thin-mode DSN: oracle://user:pwd@host:port/service_name
        dsn = oracledb.makedsn(host, port, service_name=service_name)
        self._conn = oracledb.connect(
            user=self.config.get("username", "system"),
            password=self.config.get("password", ""),
            dsn=dsn,
            encoding="UTF-8",
        )
        logger.info("Oracle connected: {}:{}", host, port)

    def close(self) -> None:
        if self._conn is not None:
            try:
                self._conn.close()
            finally:
                self._conn = None

    def execute(self, sql: str, params=None) -> QueryResult:
        if self._conn is None:
            self.connect()
        start = time.perf_counter()
        head = sql.strip().split(None, 1)[0].upper() if sql.strip() else ""
        is_dml = head in {"INSERT", "UPDATE", "DELETE", "MERGE"}

        cur = self._conn.cursor()
        try:
            cur.execute(sql, params or {})
            if is_dml:
                self._conn.commit()
                return QueryResult(
                    row_count=cur.rowcount,
                    duration_ms=int((time.perf_counter() - start) * 1000),
                    message=f"{cur.rowcount} row(s) affected",
                    is_dml=True,
                    affected_rows=cur.rowcount,
                )
            cols = [d[0] for d in cur.description] if cur.description else []
            rows = cur.fetchall()
            return QueryResult(
                columns=cols,
                rows=[list(r) for r in rows],
                row_count=len(rows),
                duration_ms=int((time.perf_counter() - start) * 1000),
            )
        finally:
            cur.close()

    def list_databases(self) -> list[str]:
        """Oracle does not have multiple databases like MySQL/Postgres.
        A "database" maps to a user/schema; return every schema the user
        can see. The configured connection user is always first."""
        if self._conn is None:
            self.connect()
        cur = self._conn.cursor()
        try:
            cur.execute("SELECT username FROM all_users ORDER BY username")
            return [r[0] for r in cur.fetchall()]
        finally:
            cur.close()

    def fetch_schema(self) -> SchemaInfo:
        if self._conn is None:
            self.connect()
        default_db = self.config.get("database", "")
        info = SchemaInfo(default_database=default_db)
        cur = self._conn.cursor()
        try:
            cur.execute("SELECT username FROM all_users ORDER BY username")
            schemas = [r[0] for r in cur.fetchall()]

            for schema in schemas:
                db_info = DatabaseInfo(name=schema)
                cur.execute(
                    "SELECT table_name, comments FROM all_tab_comments "
                    "WHERE owner = :own AND table_type='TABLE' ORDER BY table_name",
                    {"own": schema},
                )
                tables = cur.fetchall()
                for tname, tcomment in tables:
                    cur.execute(
                        "SELECT column_name, data_type, nullable "
                        "FROM all_tab_columns "
                        "WHERE owner = :own AND table_name = :tn ORDER BY column_id",
                        {"own": schema, "tn": tname},
                    )
                    cols = cur.fetchall()
                    db_info.tables.append(
                        TableInfo(
                            name=tname,
                            schema=schema,
                            comment=tcomment or "",
                            columns=[
                                ColumnInfo(
                                    name=c[0],
                                    data_type=c[1],
                                    nullable=(c[2] == "Y"),
                                )
                                for c in cols
                            ],
                        )
                    )
                info.databases.append(db_info)
        finally:
            cur.close()
        return info
