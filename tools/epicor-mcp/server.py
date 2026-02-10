"""
Epicor Kinetic Read-Only SQL Server MCP Server.

Exposes tools for schema exploration and arbitrary read-only queries
against an Epicor Kinetic SaaS SQL Server database.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import sys
from pathlib import Path
from typing import Any

import pytds
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

# ---------------------------------------------------------------------------
# Logging (stderr only -- stdout is reserved for stdio JSON-RPC transport)
# ---------------------------------------------------------------------------
logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("epicor-mcp")

# ---------------------------------------------------------------------------
# Environment / credentials
# ---------------------------------------------------------------------------
_dotenv_path = os.environ.get("DOTENV_PATH")
if _dotenv_path:
    # Resolve relative to the workspace root (cwd when Cursor launches us)
    load_dotenv(Path.cwd() / _dotenv_path)
else:
    load_dotenv()  # default .env search

HOST = os.environ["EPICOR_KINETIC_READ_ONLY_SQL_SERVER_HOST"]
PORT = int(os.environ["EPICOR_KINETIC_READ_ONLY_SQL_SERVER_PORT"])
USER = os.environ["EPICOR_KINETIC_READ_ONLY_SQL_SERVER_USERNAME"]
PASS = os.environ["EPICOR_KINETIC_READ_ONLY_SQL_SERVER_PASSWORD"]
DB = os.environ["EPICOR_KINETIC_READ_ONLY_SQL_SERVER_DATABASE"]

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
MAX_RETRIES = 5
QUERY_TIMEOUT = 30  # seconds
MAX_ROWS_HARD_LIMIT = 500
DEFAULT_MAX_ROWS = 100

# Columns to skip when auto-selecting columns for sample_data
SYSTEM_COLUMNS = frozenset({
    "SysRevID", "SysRowID", "GlobalLock", "GlbCompany",
})

# DML / DDL keywords that should never appear in user queries
FORBIDDEN_KEYWORDS = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|CREATE|EXEC|EXECUTE|MERGE|GRANT|REVOKE|DENY)\b",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def _connect() -> pytds.Connection:
    """Create a fresh pytds connection to Epicor SaaS."""
    return pytds.connect(
        server=HOST,
        port=PORT,
        user=USER,
        password=PASS,
        database=DB,
        as_dict=True,
        login_timeout=15,
        timeout=QUERY_TIMEOUT,
        enc_login_only=True,
    )


def _execute_sync(sql: str, max_rows: int = DEFAULT_MAX_ROWS) -> list[dict[str, Any]]:
    """
    Execute *sql* with retry logic.  Returns a list of row-dicts.

    Opens a fresh connection per call (most reliable with Epicor SaaS proxy).
    """
    last_err: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            conn = _connect()
            try:
                cur = conn.cursor()
                cur.execute(sql)
                rows: list[dict[str, Any]] = cur.fetchmany(max_rows)
                return rows
            finally:
                conn.close()
        except Exception as exc:
            last_err = exc
            import time
            wait = 1.5 * (attempt + 1)
            log.warning("Query attempt %d failed (%s), retrying in %.1fs…", attempt + 1, exc, wait)
            time.sleep(wait)
    raise ConnectionError(f"Query failed after {MAX_RETRIES} attempts: {last_err}")


async def execute_query(sql: str, max_rows: int = DEFAULT_MAX_ROWS) -> list[dict[str, Any]]:
    """Async wrapper around the synchronous DB call."""
    return await asyncio.to_thread(_execute_sync, sql, max_rows)


def _execute_paginated_sync(
    sql_template: str,
    batch_size: int = 25,
    max_total: int = MAX_ROWS_HARD_LIMIT,
) -> list[dict[str, Any]]:
    """
    Fetch a large result set in paginated batches to work around
    Epicor SaaS proxy limits (~30 row cap on metadata queries).

    *sql_template* must contain ``{offset}`` and ``{batch}`` placeholders.
    Example: "SELECT ... ORDER BY x OFFSET {offset} ROWS FETCH NEXT {batch} ROWS ONLY"
    """
    all_rows: list[dict[str, Any]] = []
    offset = 0
    while offset < max_total:
        sql = sql_template.format(offset=offset, batch=batch_size)
        batch = _execute_sync(sql, max_rows=batch_size)
        all_rows.extend(batch)
        if len(batch) < batch_size:
            break  # last page
        offset += batch_size
    return all_rows


async def execute_paginated(
    sql_template: str,
    batch_size: int = 25,
    max_total: int = MAX_ROWS_HARD_LIMIT,
) -> list[dict[str, Any]]:
    """Async wrapper for paginated fetches."""
    return await asyncio.to_thread(
        _execute_paginated_sync, sql_template, batch_size, max_total
    )


def _validate_sql(sql: str) -> None:
    """Raise ValueError if *sql* contains forbidden DML/DDL keywords."""
    stripped = sql.strip()
    if not stripped:
        raise ValueError("Empty SQL statement.")
    match = FORBIDDEN_KEYWORDS.search(stripped)
    if match:
        raise ValueError(
            f"Forbidden keyword '{match.group()}' detected. "
            "Only SELECT / WITH queries are allowed."
        )


def _rows_to_markdown(rows: list[dict[str, Any]]) -> str:
    """Format a list of row-dicts as a Markdown table."""
    if not rows:
        return "_No rows returned._"
    headers = list(rows[0].keys())
    lines: list[str] = []
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("| " + " | ".join("---" for _ in headers) + " |")
    for row in rows:
        vals = []
        for h in headers:
            v = row[h]
            if v is None:
                vals.append("")
            elif isinstance(v, bytes):
                vals.append(f"(bytes:{len(v)})")
            else:
                vals.append(str(v).replace("|", "\\|").replace("\n", " "))
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# FastMCP server
# ---------------------------------------------------------------------------
mcp = FastMCP("epicor-db")


# ---- Tool 1: query ----------------------------------------------------------
@mcp.tool()
async def query(sql: str, max_rows: int = DEFAULT_MAX_ROWS) -> str:
    """Run an arbitrary read-only SQL query against the Epicor database.

    Only SELECT and WITH (CTE) statements are allowed.
    Results are returned as a Markdown table.

    Args:
        sql: The SQL SELECT statement to execute.
        max_rows: Maximum rows to return (default 100, hard max 500).
    """
    _validate_sql(sql)
    max_rows = min(max_rows, MAX_ROWS_HARD_LIMIT)
    rows = await execute_query(sql, max_rows)
    result = _rows_to_markdown(rows)
    if len(rows) == max_rows:
        result += f"\n\n_Results truncated at {max_rows} rows._"
    return result


# ---- Tool 2: list_schemas ---------------------------------------------------
@mcp.tool()
async def list_schemas() -> str:
    """List all database schemas with their table counts and approximate total rows.

    Useful as a starting point to understand the database structure.
    Key schemas: Erp (core ERP data), Ice (system/metadata), IM (staging/import).
    """
    rows = await execute_query("""
        SELECT
            s.name                          AS schema_name,
            COUNT(DISTINCT t.object_id)     AS table_count,
            SUM(p.rows)                     AS approx_total_rows
        FROM sys.schemas s
        JOIN sys.tables  t ON s.schema_id = t.schema_id
        JOIN sys.partitions p ON t.object_id = p.object_id AND p.index_id IN (0,1)
        GROUP BY s.name
        ORDER BY SUM(p.rows) DESC
    """, max_rows=50)
    return _rows_to_markdown(rows)


# ---- Tool 3: list_tables ----------------------------------------------------
@mcp.tool()
async def list_tables(schema: str, name_filter: str = "") -> str:
    """List tables in a schema with row counts and column counts.

    Args:
        schema: Schema name (e.g. 'Erp', 'Ice', 'IM').
        name_filter: Optional LIKE pattern to filter table names (e.g. 'Order%').
                     Omit or pass empty string for all tables.
    """
    like_clause = ""
    if name_filter:
        safe = name_filter.replace("'", "''")
        like_clause = f"AND t.name LIKE '{safe}'"

    rows = await execute_query(f"""
        SELECT
            t.name                          AS table_name,
            SUM(p.rows)                     AS row_count,
            (SELECT COUNT(*)
             FROM INFORMATION_SCHEMA.COLUMNS c
             WHERE c.TABLE_SCHEMA = '{schema.replace("'", "''")}'
               AND c.TABLE_NAME  = t.name)  AS column_count
        FROM sys.tables t
        JOIN sys.schemas s ON t.schema_id = s.schema_id
        JOIN sys.partitions p ON t.object_id = p.object_id AND p.index_id IN (0,1)
        WHERE s.name = '{schema.replace("'", "''")}'
        {like_clause}
        GROUP BY t.name
        ORDER BY t.name
    """, max_rows=MAX_ROWS_HARD_LIMIT)
    header = f"**{schema}** schema — {len(rows)} tables"
    if name_filter:
        header += f" matching `{name_filter}`"
    return header + "\n\n" + _rows_to_markdown(rows)


# ---- Tool 4: describe_table -------------------------------------------------
@mcp.tool()
async def describe_table(schema: str, table: str) -> str:
    """Describe a table's columns, data types, nullability, and primary key.

    Note: Epicor tables can have 300-469 columns. Results may be large.
    Many Erp tables use Company + BusinessKey as PK; some use SysRowID.

    Args:
        schema: Schema name (e.g. 'Erp').
        table: Table name (e.g. 'Part', 'OrderHed').
    """
    safe_schema = schema.replace("'", "''")
    safe_table = table.replace("'", "''")
    obj_id_expr = f"OBJECT_ID('{safe_schema}.{safe_table}')"

    # Query 1: Column info via sys.columns (compact, avoids INFORMATION_SCHEMA
    # large-result-set flakiness with Epicor SaaS proxy).
    columns = await execute_query(f"""
        SELECT c.name AS col_name, ty.name AS data_type, c.max_length, c.is_nullable
        FROM sys.columns c
        JOIN sys.types ty ON c.system_type_id = ty.system_type_id
                         AND c.user_type_id  = ty.user_type_id
        WHERE c.object_id = {obj_id_expr}
        ORDER BY c.column_id
    """, max_rows=MAX_ROWS_HARD_LIMIT)

    if not columns:
        return f"Table `{schema}.{table}` not found or has no columns."

    # Query 2: PK columns (small result set, very reliable)
    pk_rows = await execute_query(f"""
        SELECT COL_NAME(ic.object_id, ic.column_id) AS pk_column, ic.key_ordinal
        FROM sys.indexes i
        JOIN sys.index_columns ic
          ON i.object_id = ic.object_id AND i.index_id = ic.index_id
        WHERE i.is_primary_key = 1
          AND i.object_id = {obj_id_expr}
        ORDER BY ic.key_ordinal
    """, max_rows=20)

    pk_col_set = {r["pk_column"] for r in pk_rows}
    pk_desc = ", ".join(
        r["pk_column"] for r in sorted(pk_rows, key=lambda r: r["key_ordinal"])
    )

    # Query 3: Row count (small, reliable)
    count_rows = await execute_query(f"""
        SELECT SUM(p.rows) AS row_count
        FROM sys.tables t
        JOIN sys.schemas s ON t.schema_id = s.schema_id
        JOIN sys.partitions p ON t.object_id = p.object_id AND p.index_id IN (0,1)
        WHERE s.name = '{safe_schema}' AND t.name = '{safe_table}'
    """, max_rows=1)
    row_count = count_rows[0]["row_count"] if count_rows else "?"

    # Build output
    lines: list[str] = [
        f"## {schema}.{table}",
        f"**Rows**: {row_count:,}" if isinstance(row_count, int) else f"**Rows**: {row_count}",
        f"**Primary Key**: {pk_desc}" if pk_desc else "**Primary Key**: _(none or SysRowID)_",
        f"**Columns**: {len(columns)}",
        "",
        "| # | Column | Type | Nullable | PK |",
        "| --- | --- | --- | --- | --- |",
    ]
    for i, c in enumerate(columns, 1):
        dtype = c["data_type"]
        ml = c["max_length"]
        # nvarchar stores 2 bytes per char; show logical length
        if dtype in ("nvarchar", "nchar") and ml is not None and ml > 0:
            dtype += f"({ml // 2})"
        elif ml is not None and ml > 0 and dtype in ("varchar", "char", "varbinary"):
            dtype += f"({ml})"
        elif ml == -1:
            dtype += "(max)"
        pk_flag = "PK" if c["col_name"] in pk_col_set else ""
        nullable = "YES" if c["is_nullable"] else "NO"
        lines.append(f"| {i} | {c['col_name']} | {dtype} | {nullable} | {pk_flag} |")

    return "\n".join(lines)


# ---- Tool 5: search_columns -------------------------------------------------
@mcp.tool()
async def search_columns(column_name: str, schema: str = "Erp") -> str:
    """Search for columns by name across all tables in a schema.

    Useful for discovering which tables reference a given entity
    (e.g., 'PartNum' appears in 319 Erp tables).

    Args:
        column_name: Column name pattern (supports SQL LIKE wildcards, e.g. '%PartNum%').
        schema: Schema to search (default 'Erp').
    """
    safe_schema = schema.replace("'", "''")
    safe_col = column_name.replace("'", "''")

    # Add wildcards if the user didn't provide any
    if "%" not in safe_col and "_" not in safe_col:
        safe_col = f"%{safe_col}%"

    rows = await execute_query(f"""
        SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = '{safe_schema}'
          AND COLUMN_NAME LIKE '{safe_col}'
        ORDER BY TABLE_NAME, COLUMN_NAME
    """, max_rows=200)

    header = f"Found {len(rows)} columns matching `{column_name}` in **{schema}** schema"
    if len(rows) == 200:
        header += " _(truncated at 200)_"
    return header + "\n\n" + _rows_to_markdown(rows)


# ---- Tool 6: find_related_tables --------------------------------------------
@mcp.tool()
async def find_related_tables(schema: str, table: str) -> str:
    """Infer tables related to the given table via shared column names.

    Epicor does NOT use SQL foreign key constraints on core tables.
    Relationships are application-level, discoverable through column naming
    conventions (e.g., PartNum, CustNum, OrderNum, VendorNum, JobNum).

    This tool finds:
    - **Likely children**: tables that contain this table's PK columns
    - **Likely parents**: tables whose PK columns appear in this table

    Args:
        schema: Schema name (e.g. 'Erp').
        table: Table name (e.g. 'Part', 'OrderHed').
    """
    safe_schema = schema.replace("'", "''")
    safe_table = table.replace("'", "''")

    # 1. Get PK columns of the target table
    pk_rows = await execute_query(f"""
        SELECT COL_NAME(ic.object_id, ic.column_id) AS pk_column
        FROM sys.indexes i
        JOIN sys.index_columns ic
          ON i.object_id = ic.object_id AND i.index_id = ic.index_id
        WHERE i.is_primary_key = 1
          AND i.object_id = OBJECT_ID('{safe_schema}.{safe_table}')
        ORDER BY ic.key_ordinal
    """, max_rows=20)

    pk_cols = [r["pk_column"] for r in pk_rows]

    if not pk_cols:
        return (
            f"Cannot determine PK for `{schema}.{table}`. "
            "It may use SysRowID as PK (no business-key relationship discovery possible)."
        )

    # Filter out 'Company' since nearly every table has it
    business_keys = [c for c in pk_cols if c != "Company"]
    if not business_keys:
        return f"`{schema}.{table}` PK is only `Company` — cannot infer relationships."

    # 2. Find tables that have ALL the business-key columns (likely children)
    # Build a query that checks for existence of each business-key column
    conditions = " AND ".join(
        f"EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS c2 "
        f"WHERE c2.TABLE_SCHEMA = c.TABLE_SCHEMA "
        f"AND c2.TABLE_NAME = c.TABLE_NAME "
        f"AND c2.COLUMN_NAME = '{bk.replace(chr(39), chr(39)*2)}')"
        for bk in business_keys
    )

    children = await execute_query(f"""
        SELECT DISTINCT c.TABLE_NAME
        FROM INFORMATION_SCHEMA.COLUMNS c
        WHERE c.TABLE_SCHEMA = '{safe_schema}'
          AND c.TABLE_NAME != '{safe_table}'
          AND {conditions}
        ORDER BY c.TABLE_NAME
    """, max_rows=200)

    # 3. Find this table's non-PK columns that look like FK references to other tables
    #    (known Epicor patterns)
    known_key_patterns = {
        "PartNum": "Part",
        "CustNum": "Customer",
        "VendorNum": "Vendor",
        "OrderNum": "OrderHed",
        "JobNum": "JobHead",
        "InvoiceNum": "InvcHead",
        "PONum": "POHeader",
        "QuoteNum": "QuoteHed",
        "PackNum": "ShipHead",
        "EmpID": "EmpBasic",
        "BuyerID": "PurAgent",
        "CurrencyCode": "Currency",
        "TaxCode": "SalesTax",
        "ShipViaCode": "ShipVia",
        "TermsCode": "Terms",
        "PlantID": "Plant",
    }

    # Get columns of this table
    cols = await execute_query(f"""
        SELECT COLUMN_NAME
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = '{safe_schema}'
          AND TABLE_NAME  = '{safe_table}'
    """, max_rows=MAX_ROWS_HARD_LIMIT)

    col_names = {r["COLUMN_NAME"] for r in cols}
    parent_refs: list[str] = []
    for col, parent_table in known_key_patterns.items():
        if col in col_names and parent_table != table:
            parent_refs.append(f"- `{col}` → likely references **{schema}.{parent_table}**")

    # 4. Build result
    lines: list[str] = [f"## Relationships for {schema}.{table}", ""]

    lines.append(f"**PK columns**: {', '.join(pk_cols)}")
    lines.append("")

    if parent_refs:
        lines.append(f"### Likely Parents ({len(parent_refs)})")
        lines.append("_Columns in this table that reference other tables:_")
        lines.extend(parent_refs)
        lines.append("")

    if children:
        child_names = [r["TABLE_NAME"] for r in children]
        lines.append(f"### Likely Children ({len(child_names)} tables share business key: {', '.join(business_keys)})")
        for name in child_names:
            lines.append(f"- {schema}.{name}")
        if len(child_names) == 200:
            lines.append("_(truncated at 200)_")
    else:
        lines.append("### Likely Children")
        lines.append("_No tables found sharing this table's business-key columns._")

    return "\n".join(lines)


# ---- Tool 7: sample_data ----------------------------------------------------
@mcp.tool()
async def sample_data(
    schema: str,
    table: str,
    max_rows: int = 5,
    columns: str = "",
) -> str:
    """Preview sample rows from a table.

    Epicor tables often have 300+ columns, so this tool auto-selects
    the most useful columns if you don't specify them.

    Args:
        schema: Schema name (e.g. 'Erp').
        table: Table name (e.g. 'Part').
        max_rows: Number of rows to return (default 5, max 50).
        columns: Comma-separated column names to include.
                 If empty, auto-selects PK + first 10 business columns.
    """
    safe_schema = schema.replace("'", "''")
    safe_table = table.replace("'", "''")
    max_rows = min(max_rows, 50)

    if columns.strip():
        # User specified columns — use them directly
        col_list = ", ".join(
            c.strip().replace("'", "''") for c in columns.split(",") if c.strip()
        )
    else:
        # Auto-select: PK columns + first 10 non-system columns
        pk_rows = await execute_query(f"""
            SELECT COL_NAME(ic.object_id, ic.column_id) AS pk_column, ic.key_ordinal
            FROM sys.indexes i
            JOIN sys.index_columns ic
              ON i.object_id = ic.object_id AND i.index_id = ic.index_id
            WHERE i.is_primary_key = 1
              AND i.object_id = OBJECT_ID('{safe_schema}.{safe_table}')
            ORDER BY ic.key_ordinal
        """, max_rows=20)
        pk_col_names = [r["pk_column"] for r in pk_rows]

        all_cols = await execute_query(f"""
            SELECT COLUMN_NAME
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = '{safe_schema}'
              AND TABLE_NAME  = '{safe_table}'
            ORDER BY ORDINAL_POSITION
        """, max_rows=MAX_ROWS_HARD_LIMIT)

        non_pk_cols = [
            r["COLUMN_NAME"] for r in all_cols
            if r["COLUMN_NAME"] not in SYSTEM_COLUMNS
            and r["COLUMN_NAME"] not in pk_col_names
        ][:10]

        selected = pk_col_names + non_pk_cols
        if not selected:
            return f"Table `{schema}.{table}` not found or has no columns."
        col_list = ", ".join(f"[{c}]" for c in selected)

    sql = f"SELECT TOP {max_rows} {col_list} FROM [{safe_schema}].[{safe_table}]"
    _validate_sql(sql)
    rows = await execute_query(sql, max_rows)
    return f"**{schema}.{table}** — {len(rows)} sample rows\n\n" + _rows_to_markdown(rows)


# ---- Resource: schema-overview -----------------------------------------------
@mcp.resource("epicor://schema-overview")
async def schema_overview() -> str:
    """High-level overview of the Epicor database schemas and key characteristics."""
    schemas = await execute_query("""
        SELECT
            s.name                          AS schema_name,
            COUNT(DISTINCT t.object_id)     AS table_count,
            SUM(p.rows)                     AS approx_total_rows
        FROM sys.schemas s
        JOIN sys.tables  t ON s.schema_id = t.schema_id
        JOIN sys.partitions p ON t.object_id = p.object_id AND p.index_id IN (0,1)
        GROUP BY s.name
        ORDER BY SUM(p.rows) DESC
    """, max_rows=50)

    top_tables = await execute_query("""
        SELECT TOP 20
            t.name                          AS table_name,
            SUM(p.rows)                     AS row_count
        FROM sys.tables t
        JOIN sys.schemas s ON t.schema_id = s.schema_id
        JOIN sys.partitions p ON t.object_id = p.object_id AND p.index_id IN (0,1)
        WHERE s.name = 'Erp'
        GROUP BY t.name
        ORDER BY SUM(p.rows) DESC
    """, max_rows=20)

    lines: list[str] = [
        "# Epicor Kinetic Database Overview",
        "",
        "## Key Characteristics",
        "- **No FK constraints on core Erp tables** — relationships are application-level",
        "- **Column naming conventions** reveal relationships (PartNum, CustNum, OrderNum, etc.)",
        "- **Tables are very wide** — InvcHead has 469 columns, Part has 293",
        "- **Every table** has SysRevID (timestamp) and SysRowID (uniqueidentifier)",
        "- **Multi-tenant** — nearly every table starts with a Company column",
        "",
        "## Schemas",
        "",
        _rows_to_markdown(schemas),
        "",
        "## Top 20 Largest Erp Tables (by row count)",
        "",
        _rows_to_markdown(top_tables),
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
