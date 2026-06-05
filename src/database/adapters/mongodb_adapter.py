"""MongoDB adapter using pymongo.

Mongo is not SQL, so `execute()` accepts a JSON pipeline (parsed by the
caller) or a `find()` JSON envelope. Results are normalised into QueryResult.
"""
from __future__ import annotations

import json
import time
from typing import Any

from pymongo import MongoClient
from pymongo.errors import PyMongoError

from src.database.adapters.base import (
    BaseAdapter,
    ColumnInfo,
    DatabaseInfo,
    QueryResult,
    SchemaInfo,
    TableInfo,
)
from src.core.logger import logger

_DEFAULT_PORT = 27017


class MongoDBAdapter(BaseAdapter):
    db_type = "mongodb"

    def connect(self) -> None:
        host = self.config.get("host", "127.0.0.1")
        port = int(self.config.get("port") or _DEFAULT_PORT)
        user = self.config.get("username")
        pwd = self.config.get("password")
        auth = f"{user}:{pwd}@" if user else ""
        uri = f"mongodb://{auth}{host}:{port}/"
        self._conn = MongoClient(uri, serverSelectionTimeoutMS=5000)
        # Trigger a server check now so failures surface early.
        self._conn.admin.command("ping")
        logger.info("MongoDB connected: {}", uri)

    def close(self) -> None:
        if self._conn is not None:
            try:
                self._conn.close()
            finally:
                self._conn = None

    # ------------------------------------------------------------------ #
    def execute(self, sql: str, params=None) -> QueryResult:
        """`sql` here is actually a JSON envelope:

            {"collection": "users", "pipeline": [...]}     # aggregation
            {"collection": "users", "find": {...}, "limit": 10}
        """
        if self._conn is None:
            self.connect()
        start = time.perf_counter()

        try:
            payload = json.loads(sql)
            db = self._conn[self.config.get("database")]
            coll = db[payload["collection"]]

            if "pipeline" in payload:
                docs = list(coll.aggregate(payload["pipeline"]))
            else:
                cursor = coll.find(payload.get("find") or {})
                if "limit" in payload:
                    cursor = cursor.limit(int(payload["limit"]))
                docs = list(cursor)
        except (PyMongoError, KeyError, json.JSONDecodeError) as exc:
            return QueryResult(
                row_count=0,
                duration_ms=int((time.perf_counter() - start) * 1000),
                message=f"Error: {exc}",
            )

        # Normalise: collect all top-level keys, plus "_id" stringified.
        cols: list[str] = []
        seen: set[str] = set()
        rows: list[list[Any]] = []
        for d in docs:
            d = dict(d)
            if "_id" in d:
                d["_id"] = str(d["_id"])
            for k in d.keys():
                if k not in seen:
                    seen.add(k)
                    cols.append(k)
            rows.append([d.get(c) for c in cols])

        return QueryResult(
            columns=cols,
            rows=rows,
            row_count=len(rows),
            duration_ms=int((time.perf_counter() - start) * 1000),
        )

    def list_databases(self) -> list[str]:
        if self._conn is None:
            self.connect()
        return [n for n in self._conn.list_database_names() if n not in ("admin", "local", "config")]

    def fetch_schema(self) -> SchemaInfo:
        if self._conn is None:
            self.connect()
        default_db = self.config.get("database", "")
        info = SchemaInfo(default_database=default_db)

        for db_name in self.list_databases():
            db = self._conn[db_name]
            db_info = DatabaseInfo(name=db_name)
            for cname in db.list_collection_names():
                sample = db[cname].find_one() or {}
                fields = [
                    ColumnInfo(name=k, data_type=type(v).__name__)
                    for k, v in sample.items()
                ]
                db_info.tables.append(TableInfo(name=cname, schema=db_name, columns=fields))
            info.databases.append(db_info)
        return info
