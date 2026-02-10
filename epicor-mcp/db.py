"""
Database connection management for Epicor MCP server.

Provides a singleton connection to the Epicor SQL Server (read-only)
with eager connection, auto-reconnect, read-only enforcement, and
configurable row limits.
"""

from __future__ import annotations

import os
import re
import sys
import time
from pathlib import Path
from typing import Any

import pytds

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_BLOCKED_KEYWORDS = [
    "INSERT", "UPDATE", "DELETE", "DROP", "CREATE", "ALTER",
    "TRUNCATE", "EXEC", "EXECUTE", "GRANT", "REVOKE", "MERGE",
]

_BLOCKED_PATTERN = re.compile(
    r"\b(" + "|".join(_BLOCKED_KEYWORDS) + r")\b",
    re.IGNORECASE,
)

DEFAULT_MAX_ROWS = 500
ABSOLUTE_MAX_ROWS = 10_000
REQUEST_TIMEOUT = 120  # seconds


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_env() -> None:
    """Load .env from workspace root (CWD) if python-dotenv is available."""
    try:
        from dotenv import load_dotenv
        # Walk up from this file to find .env in the workspace root
        env_path = Path(__file__).resolve().parent.parent / ".env"
        if env_path.exists():
            load_dotenv(env_path)
            print(f"Loaded .env from {env_path}", file=sys.stderr)
        else:
            # Also try CWD (Cursor sets CWD to workspace root)
            cwd_env = Path.cwd() / ".env"
            if cwd_env.exists():
                load_dotenv(cwd_env)
                print(f"Loaded .env from {cwd_env}", file=sys.stderr)
    except ImportError:
        pass  # dotenv not installed, rely on environment variables


def _strip_comments(sql: str) -> str:
    """Remove SQL comments for safety checking (not for execution)."""
    # Remove single-line comments
    sql = re.sub(r"--[^\n]*", "", sql)
    # Remove multi-line comments
    sql = re.sub(r"/\*.*?\*/", "", sql, flags=re.DOTALL)
    return sql


# ---------------------------------------------------------------------------
# Database class
# ---------------------------------------------------------------------------

class EpicorDB:
    """Manages a read-only connection to the Epicor SQL Server database."""

    def __init__(self) -> None:
        _load_env()

        self._host = os.environ.get("SQL_SERVER_HOST", "")
        self._database = os.environ.get("SQL_SERVER_DATABASE", "")
        self._user = os.environ.get("SQL_SERVER_USER", "")
        self._password = os.environ.get("SQL_SERVER_PASSWORD", "")
        self._port = int(os.environ.get("SQL_SERVER_PORT", "1433"))

        if not all([self._host, self._database, self._user, self._password]):
            raise RuntimeError(
                "Missing SQL Server credentials. "
                "Set SQL_SERVER_HOST, SQL_SERVER_DATABASE, SQL_SERVER_USER, "
                "SQL_SERVER_PASSWORD in .env or environment."
            )

        self._conn: pytds.Connection | None = None
        self._connect()

    # -- Connection management -----------------------------------------------

    def _connect(self) -> None:
        """Establish connection to SQL Server."""
        t0 = time.monotonic()
        try:
            self._conn = pytds.connect(
                self._host,
                database=self._database,
                user=self._user,
                password=self._password,
                port=self._port,
                timeout=REQUEST_TIMEOUT,
                login_timeout=30,
                autocommit=True,
            )
            elapsed = time.monotonic() - t0
            print(
                f"Connected to {self._host}:{self._port}/{self._database} "
                f"in {elapsed:.1f}s",
                file=sys.stderr,
            )
        except Exception as exc:
            raise RuntimeError(
                f"Failed to connect to Epicor DB at "
                f"{self._host}:{self._port}: {exc}"
            ) from exc

    def _reconnect(self) -> None:
        """Close and re-establish the connection."""
        print("Reconnecting to Epicor DB...", file=sys.stderr)
        if self._conn:
            try:
                self._conn.close()
            except Exception:
                pass
        self._conn = None
        self._connect()

    def _ensure_connection(self) -> pytds.Connection:
        """Return active connection, reconnecting if necessary."""
        if self._conn is None:
            self._reconnect()
        return self._conn  # type: ignore[return-value]

    # -- Query execution -----------------------------------------------------

    def execute(
        self,
        sql: str,
        params: tuple[Any, ...] | None = None,
        max_rows: int = DEFAULT_MAX_ROWS,
    ) -> tuple[list[str], list[tuple[Any, ...]]]:
        """
        Execute a read-only SQL query and return (columns, rows).

        - Validates the query is read-only (blocks DML/DDL keywords).
        - Injects TOP N if not already present and max_rows > 0.
        - Auto-reconnects on connection errors and retries once.

        Returns:
            (column_names, rows) where rows is a list of tuples.
        """
        self._validate_readonly(sql)

        # Inject TOP if not present
        if max_rows > 0:
            max_rows = min(max_rows, ABSOLUTE_MAX_ROWS)
            sql = self._inject_top(sql, max_rows)

        return self._execute_with_retry(sql, params)

    def execute_raw(
        self,
        sql: str,
        params: tuple[Any, ...] | None = None,
    ) -> tuple[list[str], list[tuple[Any, ...]]]:
        """
        Execute a query without row-limit injection (for metadata queries).
        Still enforces read-only.
        """
        self._validate_readonly(sql)
        return self._execute_with_retry(sql, params)

    def _execute_with_retry(
        self,
        sql: str,
        params: tuple[Any, ...] | None = None,
    ) -> tuple[list[str], list[tuple[Any, ...]]]:
        """Execute query, retrying once on connection error."""
        for attempt in range(2):
            try:
                conn = self._ensure_connection()
                cur = conn.cursor()
                if params:
                    cur.execute(sql, params)
                else:
                    cur.execute(sql)

                if cur.description is None:
                    return [], []

                columns = [desc[0] for desc in cur.description]
                rows = cur.fetchall()
                return columns, rows

            except (pytds.ClosedConnectionError, OSError, ConnectionError) as exc:
                if attempt == 0:
                    print(
                        f"Connection error ({type(exc).__name__}), retrying...",
                        file=sys.stderr,
                    )
                    self._reconnect()
                else:
                    raise RuntimeError(
                        f"Query failed after reconnect: {exc}"
                    ) from exc

        # Should not reach here
        return [], []

    # -- Safety --------------------------------------------------------------

    @staticmethod
    def _validate_readonly(sql: str) -> None:
        """Raise if the query contains blocked keywords."""
        cleaned = _strip_comments(sql)
        match = _BLOCKED_PATTERN.search(cleaned)
        if match:
            raise ValueError(
                f"Query blocked: contains disallowed keyword '{match.group()}'. "
                f"Only SELECT / WITH queries are allowed."
            )

    @staticmethod
    def _inject_top(sql: str, max_rows: int) -> str:
        """
        Inject TOP N into a SELECT if not already present.
        Handles simple SELECT and WITH...SELECT patterns.
        """
        stripped = sql.strip()

        # Skip if TOP is already present
        if re.search(r"\bTOP\s+\d+", stripped, re.IGNORECASE):
            return sql

        # Handle WITH ... SELECT pattern
        if stripped.upper().startswith("WITH"):
            # Find the final SELECT after the CTE
            # We inject TOP into the last SELECT
            last_select = None
            for m in re.finditer(r"\bSELECT\b", stripped, re.IGNORECASE):
                last_select = m
            if last_select:
                pos = last_select.end()
                return stripped[:pos] + f" TOP {max_rows}" + stripped[pos:]
            return sql

        # Simple SELECT
        match = re.match(r"(\s*SELECT\b)", stripped, re.IGNORECASE)
        if match:
            pos = match.end()
            return stripped[:pos] + f" TOP {max_rows}" + stripped[pos:]

        return sql


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_db: EpicorDB | None = None


def get_db() -> EpicorDB:
    """Get or create the singleton database connection."""
    global _db
    if _db is None:
        _db = EpicorDB()
    return _db
