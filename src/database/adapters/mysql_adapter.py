"""MySQL adapter using SQLAlchemy + PyMySQL."""
from __future__ import annotations

import time

import pymysql
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from src.database.adapters.base import (
    BaseAdapter,
    ColumnInfo,
    DatabaseInfo,
    QueryResult,
    SchemaInfo,
    TableInfo,
)
from src.core.logger import logger

_DEFAULT_PORT = 3306


def _escape_percent_for_pymysql(sql: str) -> str:
    """pymysql 内部用 `%` 格式化参数；SQL 字符串字面量 / 注释里的字面量 `%`
    必须先转义为 `%%`，否则 ``LIKE '%sl%'`` 这类会触发
    ``TypeError: not enough arguments for format string``。

    例：
      ``LIKE '%sl%'``        -> ``LIKE '%%sl%%'``
      ``WHERE id = %s``      -> ``WHERE id = %s``   (占位符不动)
      ``-- 100% match``      -> ``-- 100%% match``  (行注释里也转义)
      ``WHERE x = 'a%'``     -> ``WHERE x = 'a%%'``
    """
    out: list[str] = []
    i, n = 0, len(sql)
    while i < n:
        c = sql[i]
        # 1) 单/双引号字符串字面量 —— 整段原样输出，但 % → %%
        if c in ("'", '"'):
            quote = c
            j = i + 1
            while j < n:
                if sql[j] == "\\" and j + 1 < n:
                    j += 2
                    continue
                if sql[j] == quote:
                    if j + 1 < n and sql[j + 1] == quote:
                        # '' / "" —— 双重引号转义
                        j += 2
                        continue
                    j += 1
                    break
                j += 1
            out.append(sql[i:j].replace("%", "%%"))
            i = j
            continue
        # 2) 反引号标识符 —— 整段原样输出
        if c == "`":
            j = sql.find("`", i + 1)
            if j == -1:
                out.append(sql[i:])
                i = n
            else:
                out.append(sql[i:j + 1].replace("%", "%%"))
                i = j + 1
            continue
        # 3) -- 行注释 —— 整段原样输出，% → %%
        if c == "-" and i + 1 < n and sql[i + 1] == "-":
            j = sql.find("\n", i)
            if j == -1:
                out.append(sql[i:].replace("%", "%%"))
                i = n
            else:
                out.append(sql[i:j].replace("%", "%%"))
                i = j
            continue
        # 4) /* 块注释 —— 整段原样输出，% → %%
        if c == "/" and i + 1 < n and sql[i + 1] == "*":
            j = sql.find("*/", i + 2)
            if j == -1:
                out.append(sql[i:].replace("%", "%%"))
                i = n
            else:
                out.append(sql[i:j + 2].replace("%", "%%"))
                i = j + 2
            continue
        # 5) 代码区 —— 只处理占位符风格的 %
        if c == "%":
            nxt = sql[i + 1] if i + 1 < n else ""
            if nxt in "%sdfi":
                out.append(c)  # 占位符，原样
            else:
                out.append("%%")  # 字面量，转义
            i += 1
            continue
        # 6) 其他字符
        out.append(c)
        i += 1
    return "".join(out)


class MySQLAdapter(BaseAdapter):
    db_type = "mysql"

    def _dsn(self) -> str:
        host = self.config.get("host", "127.0.0.1")
        port = self.config.get("port") or _DEFAULT_PORT
        database = self.config.get("database", "")
        user = self.config.get("username", "root")
        password = self.config.get("password", "")
        return (
            f"mysql+pymysql://{user}:{password}@{host}:{port}/{database}"
            "?charset=utf8mb4"
        )

    def _engine(self) -> Engine:
        return create_engine(self._dsn(), pool_pre_ping=True, future=True)

    # ------------------------------------------------------------------ #
    def connect(self) -> None:
        # Open a short-lived raw PyMySQL connection for direct operations.
        host = self.config.get("host", "127.0.0.1")
        port = self.config.get("port") or _DEFAULT_PORT
        self._conn = pymysql.connect(
            host=host,
            port=int(port),
            user=self.config.get("username", "root"),
            password=self.config.get("password", ""),
            database=self.config.get("database") or None,
            charset="utf8mb4",
            autocommit=True,
            connect_timeout=10,
        )
        logger.info("MySQL connected: {}:{}", host, port)

    def close(self) -> None:
        if self._conn is not None:
            try:
                self._conn.close()
            finally:
                self._conn = None

    # ------------------------------------------------------------------ #
    def execute(self, sql: str, params=None) -> QueryResult:
        if self._conn is None:
            self.connect()
        start = time.perf_counter()
        stripped = sql.strip().rstrip(";").strip()
        head = stripped.split(None, 1)[0].upper() if stripped else ""
        is_dml = head in {"INSERT", "UPDATE", "DELETE", "REPLACE", "MERGE"}

        cur = self._conn.cursor()
        try:
            # pymysql 内部用 `%` 格式化 args；先转义字面量 %，否则 LIKE '%x%'
            # 这类 SQL 会触发 "not enough arguments for format string"。
            cur.execute(_escape_percent_for_pymysql(sql), params or ())
            if is_dml:
                affected = cur.rowcount
                return QueryResult(
                    row_count=affected,
                    duration_ms=int((time.perf_counter() - start) * 1000),
                    message=f"{affected} row(s) affected",
                    is_dml=True,
                    affected_rows=affected,
                )
            rows = cur.fetchall()
            cols = [d[0] for d in cur.description] if cur.description else []
            return QueryResult(
                columns=cols,
                rows=[list(r) for r in rows],
                row_count=len(rows),
                duration_ms=int((time.perf_counter() - start) * 1000),
            )
        finally:
            cur.close()

    # ------------------------------------------------------------------ #
    def list_databases(self) -> list[str]:
        engine = self._engine()
        with engine.connect() as conn:
            rows = conn.execute(text("SHOW DATABASES")).fetchall()
        return [r[0] for r in rows]

    def fetch_schema(self) -> SchemaInfo:
        engine = self._engine()
        default_db = self.config.get("database", "")
        info = SchemaInfo(default_database=default_db)

        with engine.connect() as conn:
            dbs = [r[0] for r in conn.execute(text("SHOW DATABASES")).fetchall()]

            for db in dbs:
                db_info = DatabaseInfo(name=db)
                tbls = conn.execute(
                    text(
                        "SELECT TABLE_NAME, TABLE_COMMENT "
                        "FROM information_schema.tables "
                        "WHERE TABLE_SCHEMA = :db AND TABLE_TYPE='BASE TABLE'"
                    ),
                    {"db": db},
                ).fetchall()
                for tname, tcomment in tbls:
                    cols = conn.execute(
                        text(
                            "SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE, COLUMN_COMMENT "
                            "FROM information_schema.columns "
                            "WHERE TABLE_SCHEMA = :db AND TABLE_NAME = :tn "
                            "ORDER BY ORDINAL_POSITION"
                        ),
                        {"db": db, "tn": tname},
                    ).fetchall()
                    db_info.tables.append(
                        TableInfo(
                            name=tname,
                            schema=db,
                            comment=tcomment or "",
                            columns=[
                                ColumnInfo(
                                    name=c[0],
                                    data_type=c[1],
                                    nullable=(c[2] == "YES"),
                                    comment=c[3] or "",
                                )
                                for c in cols
                            ],
                        )
                    )
                info.databases.append(db_info)
        return info
