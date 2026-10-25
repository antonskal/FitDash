"""SQLite connection management.

A `Database` hands out short-lived connections. SQLite in WAL mode supports
many concurrent readers alongside a single writer, which is exactly the shape
of this app: the sync worker thread writes while API requests read.
"""

from __future__ import annotations

import sqlite3
import threading
from collections.abc import Iterable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.config import get_settings

SCHEMA_PATH = Path(__file__).with_name("schema.sql")
SCHEMA_VERSION = 1


def _dict_factory(cursor: sqlite3.Cursor, row: tuple) -> dict[str, Any]:
    return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}


class Database:
    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._write_lock = threading.RLock()
        self._initialise()

    # ------------------------------------------------------------------ setup
    def _initialise(self) -> None:
        with self.connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
            version = conn.execute("PRAGMA user_version").fetchone()["user_version"]
            if version < SCHEMA_VERSION:
                conn.execute(f"PRAGMA user_version={SCHEMA_VERSION}")

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(
            self.path,
            timeout=30,
            isolation_level=None,  # autocommit; we manage transactions explicitly
            check_same_thread=False,
        )
        conn.row_factory = _dict_factory
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=30000")
        try:
            yield conn
        finally:
            conn.close()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """Serialised write transaction (readers are never blocked under WAL)."""
        with self._write_lock, self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                yield conn
            except Exception:
                conn.execute("ROLLBACK")
                raise
            else:
                conn.execute("COMMIT")

    # ---------------------------------------------------------------- helpers
    def query(self, sql: str, params: Sequence[Any] | Mapping[str, Any] = ()) -> list[dict[str, Any]]:
        with self.connect() as conn:
            return conn.execute(sql, params).fetchall()

    def query_one(self, sql: str, params: Sequence[Any] | Mapping[str, Any] = ()) -> dict[str, Any] | None:
        with self.connect() as conn:
            return conn.execute(sql, params).fetchone()

    def execute(self, sql: str, params: Sequence[Any] | Mapping[str, Any] = ()) -> None:
        with self.transaction() as conn:
            conn.execute(sql, params)

    def upsert(
        self,
        table: str,
        rows: Iterable[Mapping[str, Any]],
        conflict_cols: Sequence[str],
        conn: sqlite3.Connection | None = None,
    ) -> int:
        """Idempotent bulk upsert via `INSERT ... ON CONFLICT DO UPDATE`.

        Every non-key column present in the row is overwritten with the new
        value so late corrections from Garmin (e.g. partial intraday metrics)
        replace stale data without creating duplicates.
        """
        rows = list(rows)
        if not rows:
            return 0
        cols = list(rows[0].keys())
        placeholders = ", ".join(f":{c}" for c in cols)
        update_cols = [c for c in cols if c not in conflict_cols]
        sql = f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({placeholders})"
        if update_cols:
            assignments = ", ".join(f"{c}=excluded.{c}" for c in update_cols)
            sql += f" ON CONFLICT({', '.join(conflict_cols)}) DO UPDATE SET {assignments}"
        else:
            sql += f" ON CONFLICT({', '.join(conflict_cols)}) DO NOTHING"

        normalised = [{c: r.get(c) for c in cols} for r in rows]
        if conn is not None:
            conn.executemany(sql, normalised)
        else:
            with self.transaction() as tx:
                tx.executemany(sql, normalised)
        return len(normalised)

    def replace_for_key(
        self,
        table: str,
        key_col: str,
        key_value: Any,
        rows: Iterable[Mapping[str, Any]],
        conflict_cols: Sequence[str],
        conn: sqlite3.Connection | None = None,
    ) -> int:
        """Delete all rows for `key_col = key_value` then insert the fresh set.

        Used for child series (sleep stages, telemetry points) whose row count
        can shrink between fetches, where a plain upsert would leave orphans.
        """
        rows = list(rows)

        def _run(c: sqlite3.Connection) -> int:
            c.execute(f"DELETE FROM {table} WHERE {key_col} = ?", (key_value,))
            return self.upsert(table, rows, conflict_cols, conn=c)

        if conn is not None:
            return _run(conn)
        with self.transaction() as tx:
            return _run(tx)

    # -------------------------------------------------------------- app state
    def get_state(self, key: str, default: str | None = None) -> str | None:
        row = self.query_one("SELECT value FROM app_state WHERE key = ?", (key,))
        return row["value"] if row else default

    def set_state(self, key: str, value: str | None) -> None:
        self.upsert("app_state", [{"key": key, "value": value}], ["key"])


@lru_cache
def get_db() -> Database:
    return Database(get_settings().resolved_db_path)
