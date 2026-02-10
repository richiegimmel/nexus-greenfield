"""
Data querying tools: execute_query, sample_data.
"""

from __future__ import annotations

import datetime
from decimal import Decimal
from typing import Any

from db import get_db, DEFAULT_MAX_ROWS, ABSOLUTE_MAX_ROWS
from metadata import get_metadata


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _format_cell(value: Any, max_len: int = 200) -> str:
    """Format a cell value for markdown display."""
    if value is None:
        return "NULL"
    if isinstance(value, bytes):
        return f"<binary {len(value)} bytes>"
    if isinstance(value, datetime.datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, datetime.date):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, Decimal):
        return str(value)
    s = str(value)
    if len(s) > max_len:
        return s[:max_len] + "..."
    return s


def _results_to_markdown(
    columns: list[str],
    rows: list[tuple[Any, ...]],
    max_rows_shown: int | None = None,
    total_hint: int | None = None,
) -> str:
    """Render query results as a markdown table."""
    if not columns:
        return "(no results)"

    if not rows:
        return f"**Columns:** {', '.join(columns)}\n\n(0 rows returned)"

    # Format cells
    str_rows = []
    for row in rows:
        str_rows.append([_format_cell(v) for v in row])

    # Calculate widths
    widths = [len(h) for h in columns]
    for row in str_rows:
        for i, cell in enumerate(row):
            if i < len(widths):
                widths[i] = max(widths[i], min(len(cell), 60))

    # Truncate cells for display
    def trunc(s: str, w: int) -> str:
        if len(s) > 60:
            return s[:57] + "..."
        return s

    def fmt_row(cells: list[str]) -> str:
        return "| " + " | ".join(
            trunc(c, w).ljust(w) for c, w in zip(cells, widths)
        ) + " |"

    lines = [
        fmt_row(columns),
        "| " + " | ".join("-" * w for w in widths) + " |",
    ]
    for row in str_rows:
        lines.append(fmt_row(row))

    # Summary
    shown = len(rows)
    summary_parts = [f"{shown} rows returned"]
    if total_hint and total_hint > shown:
        summary_parts.append(f"(showing {shown} of {total_hint:,} total)")

    return "\n".join(lines) + "\n\n" + " ".join(summary_parts)


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

def execute_query(
    query: str,
    max_rows: int = DEFAULT_MAX_ROWS,
) -> str:
    """
    Execute a read-only SQL query against the Epicor database.

    Runs any SELECT query and returns results as a formatted table.
    INSERT/UPDATE/DELETE/DROP and other write operations are blocked.
    A TOP N clause is injected automatically if not present.

    Args:
        query: SQL SELECT query to execute (e.g. "SELECT TOP 100 * FROM Erp.JobHead WHERE Company = '160144'")
        max_rows: Maximum rows to return (default 500, max 10000)
    """
    db = get_db()
    max_rows = min(max(1, max_rows), ABSOLUTE_MAX_ROWS)

    try:
        columns, rows = db.execute(query, max_rows=max_rows)
        return _results_to_markdown(columns, rows)
    except ValueError as e:
        return f"**Query blocked:** {e}"
    except Exception as e:
        return f"**Query failed:** {e}"


def sample_data(
    table: str,
    schema: str = "Erp",
    limit: int = 10,
    where: str | None = None,
) -> str:
    """
    Get sample rows from an Epicor table.

    Automatically excludes binary/image columns and truncates long strings.
    Orders by primary key if detectable for representative data.

    Args:
        table: Table name (e.g. "JobHead", "Customer", "GLJrnDtl")
        schema: Schema name (default "Erp")
        limit: Number of rows to return (default 10)
        where: Optional WHERE clause without the WHERE keyword (e.g. "Company = '160144' AND JobNum LIKE 'J%'")
    """
    meta = get_metadata()
    info = meta.resolve_table(table, schema)
    if not info:
        suggestions = meta.suggest_similar(table, limit=5)
        msg = f"Table '{schema}.{table}' not found."
        if suggestions:
            msg += f"\n\nDid you mean: {', '.join(suggestions)}?"
        return msg

    db = get_db()

    # Get column info to exclude binary types
    try:
        _, col_rows = db.execute_raw(f"""
            SELECT COLUMN_NAME, DATA_TYPE
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = '{info.schema}' AND TABLE_NAME = '{info.name}'
            ORDER BY ORDINAL_POSITION
        """)
    except Exception as e:
        return f"**Error reading column info:** {e}"

    # Exclude binary/image/varbinary columns
    binary_types = {"binary", "varbinary", "image", "timestamp", "rowversion"}
    columns = [
        name for name, dtype in col_rows
        if dtype.lower() not in binary_types
    ]

    if not columns:
        return f"No displayable columns in {info.full_name}."

    # Build query
    col_list = ", ".join(f"[{c}]" for c in columns)
    sql = f"SELECT TOP {min(limit, 100)} {col_list} FROM [{info.schema}].[{info.name}]"

    if where:
        sql += f" WHERE {where}"

    # Try to order by PK for representative data
    try:
        _, pk_rows = db.execute_raw(f"""
            SELECT ku.COLUMN_NAME
            FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc
            JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE ku
                ON tc.CONSTRAINT_NAME = ku.CONSTRAINT_NAME
                AND tc.TABLE_SCHEMA = ku.TABLE_SCHEMA
            WHERE tc.CONSTRAINT_TYPE = 'PRIMARY KEY'
                AND tc.TABLE_SCHEMA = '{info.schema}'
                AND tc.TABLE_NAME = '{info.name}'
            ORDER BY ku.ORDINAL_POSITION
        """)
        if pk_rows:
            pk_cols = [r[0] for r in pk_rows]
            sql += " ORDER BY " + ", ".join(f"[{c}]" for c in pk_cols)
    except Exception:
        pass  # No PK ordering, fine

    try:
        result_cols, result_rows = db.execute_raw(sql)
        header = f"**Sample from {info.full_name}** ({len(result_rows)} rows)\n\n"
        return header + _results_to_markdown(result_cols, result_rows)
    except Exception as e:
        return f"**Query failed:** {e}"
