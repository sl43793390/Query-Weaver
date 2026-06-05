"""Redis adapter using redis-py.

The "SQL" parameter is actually a single Redis command, e.g.:

    GET user:1
    HGETALL user:1
    SCAN 0 MATCH user:* COUNT 100
"""
from __future__ import annotations

import time
from typing import Any

import redis
from redis.exceptions import RedisError

from src.database.adapters.base import (
    BaseAdapter,
    ColumnInfo,
    DatabaseInfo,
    QueryResult,
    SchemaInfo,
    TableInfo,
)
from src.core.logger import logger

_DEFAULT_PORT = 6379


class RedisAdapter(BaseAdapter):
    db_type = "redis"

    def connect(self) -> None:
        self._conn = redis.Redis(
            host=self.config.get("host", "127.0.0.1"),
            port=int(self.config.get("port") or _DEFAULT_PORT),
            db=int(self.config.get("database") or 0),
            username=self.config.get("username") or None,
            password=self.config.get("password") or None,
            socket_timeout=5,
            decode_responses=True,
        )
        self._conn.ping()
        logger.info("Redis connected")

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
        try:
            parts = sql.strip().split()
            if not parts:
                return QueryResult(message="Empty command", row_count=0)
            cmd = parts[0].upper()
            args = parts[1:]
            raw = self._conn.execute_command(cmd, *args)
        except RedisError as exc:
            return QueryResult(
                row_count=0,
                duration_ms=int((time.perf_counter() - start) * 1000),
                message=f"Error: {exc}",
            )

        return self._format_redis_result(raw, int((time.perf_counter() - start) * 1000))

    @staticmethod
    def _format_redis_result(raw: Any, duration_ms: int) -> QueryResult:
        if raw is None:
            return QueryResult(message="(nil)", duration_ms=duration_ms)
        if isinstance(raw, bool):
            return QueryResult(
                columns=["value"],
                rows=[["1" if raw else "0"]],
                row_count=1,
                duration_ms=duration_ms,
            )
        if isinstance(raw, (str, int, float, bytes)):
            return QueryResult(
                columns=["value"],
                rows=[[raw]],
                row_count=1,
                duration_ms=duration_ms,
            )
        if isinstance(raw, list):
            return QueryResult(
                columns=["value"],
                rows=[[v] for v in raw],
                row_count=len(raw),
                duration_ms=duration_ms,
            )
        if isinstance(raw, dict):
            return QueryResult(
                columns=["field", "value"],
                rows=[[k, v] for k, v in raw.items()],
                row_count=len(raw),
                duration_ms=duration_ms,
            )
        return QueryResult(
            columns=["value"],
            rows=[[str(raw)]],
            row_count=1,
            duration_ms=duration_ms,
        )

    def list_databases(self) -> list[str]:
        """Redis has 16 logical DBs by default. Return the active one,
        plus any key namespace prefix we discover via SCAN."""
        if self._conn is None:
            self.connect()
        active = int(self.config.get("database") or 0)
        return [f"db{active}"]

    def fetch_schema(self) -> SchemaInfo:
        if self._conn is None:
            self.connect()
        active = int(self.config.get("database") or 0)
        db_name = f"db{active}"
        info = SchemaInfo(default_database=db_name)
        db_info = DatabaseInfo(name=db_name)
        # Emulate tables with key namespace prefixes.
        prefixes = ("user:", "session:", "cache:", "key:")
        for p in prefixes:
            try:
                count = 0
                for _ in self._conn.scan_iter(match=f"{p}*", count=100):
                    count += 1
                    if count > 0:   # found at least one
                        break
            except RedisError:
                count = 0
            if count:
                db_info.tables.append(
                    TableInfo(
                        name=p,
                        schema=db_name,
                        columns=[
                            ColumnInfo(name="key", data_type="string"),
                            ColumnInfo(name="value", data_type="string"),
                        ],
                    )
                )
        info.databases.append(db_info)
        return info
