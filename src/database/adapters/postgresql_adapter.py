"""PostgreSQL adapter using psycopg2."""
from __future__ import annotations

import time

import psycopg2
import psycopg2.extras
from psycopg2 import sql as pgsql

from src.database.adapters.base import (
    BaseAdapter,
    ColumnInfo,
    DatabaseInfo,
    QueryResult,
    SchemaInfo,
    TableInfo,
)
from src.core.logger import logger

_DEFAULT_PORT = 5432


class PostgreSQLAdapter(BaseAdapter):
    db_type = "postgresql"

    def connect(self) -> None:
        self._conn = psycopg2.connect(
            host=self.config.get("host", "127.0.0.1"),
            port=int(self.config.get("port") or _DEFAULT_PORT),
            user=self.config.get("username", "postgres"),
            password=self.config.get("password", ""),
            dbname=self.config.get("database", "postgres"),
            connect_timeout=10,
        )
        # Return named tuples for ergonomic column access.
        self._conn.set_session(readonly=False, autocommit=True)
        logger.info("PostgreSQL connected")

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
        is_dml = head in {"INSERT", "UPDATE", "DELETE"}

        with self._conn.cursor() as cur:
            cur.execute(sql, params or None)
            if is_dml:
                affected = cur.rowcount
                return QueryResult(
                    row_count=affected,
                    duration_ms=int((time.perf_counter() - start) * 1000),
                    message=f"{affected} row(s) affected",
                    is_dml=True,
                    affected_rows=affected,
                )
            cols = [d[0] for d in cur.description] if cur.description else []
            rows = cur.fetchall()
            return QueryResult(
                columns=cols,
                rows=[list(r) for r in rows],
                row_count=len(rows),
                duration_ms=int((time.perf_counter() - start) * 1000),
            )

    def list_databases(self) -> list[str]:
        if self._conn is None:
            self.connect()
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT datname FROM pg_database "
                "WHERE datistemplate = false ORDER BY datname"
            )
            return [r[0] for r in cur.fetchall()]

    def fetch_schema(self) -> SchemaInfo:
        if self._conn is None:
            self.connect()
        default_db = self.config.get("database", "")
        info = SchemaInfo(default_database=default_db)

        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT schema_name FROM information_schema.schemata "
                "WHERE schema_name NOT IN ('pg_catalog', 'information_schema', 'pg_toast') "
                "ORDER BY schema_name"
            )
            schemas = [r[0] for r in cur.fetchall()]

            for schema in schemas:
                db_info = DatabaseInfo(name=schema)
                cur.execute(
                    "SELECT table_name, obj_description(c.oid) "
                    "FROM information_schema.tables t "
                    "JOIN pg_class c ON c.relname = t.table_name "
                    "WHERE table_schema = %s "
                    "ORDER BY table_name",
                    (schema,),
                )
                tables = cur.fetchall()
                for tname, tcomment in tables:
                    cur.execute(
                        "SELECT column_name, data_type, is_nullable "
                        "FROM information_schema.columns "
                        "WHERE table_schema=%s AND table_name=%s "
                        "ORDER BY ordinal_position",
                        (schema, tname),
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
                                    nullable=(c[2] == "YES"),
                                )
                                for c in cols
                            ],
                        )
                    )
                info.databases.append(db_info)
        return info
