"""
Schema discovery tools: list_schemas, search_tables, describe_table.
"""

from __future__ import annotations

from db import get_db
from metadata import get_metadata


def _md_table(headers: list[str], rows: list[list[str]]) -> str:
    """Render a markdown table from headers and rows."""
    if not rows:
        return "(no results)"

    # Calculate column widths
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            if i < len(widths):
                widths[i] = max(widths[i], len(str(cell)))

    def fmt_row(cells: list[str]) -> str:
        return "| " + " | ".join(
            str(c).ljust(w) for c, w in zip(cells, widths)
        ) + " |"

    lines = [
        fmt_row(headers),
        "| " + " | ".join("-" * w for w in widths) + " |",
    ]
    for row in rows:
        lines.append(fmt_row(row))
    return "\n".join(lines)


def list_schemas() -> str:
    """
    List all database schemas with table counts.

    Returns a summary of every schema in the Epicor database
    and how many tables each contains.
    """
    schemas = get_metadata().get_schemas()
    rows = [[s, str(c)] for s, c in schemas.items()]
    total = sum(schemas.values())
    table = _md_table(["Schema", "Tables"], rows)
    return f"**{len(schemas)} schemas, {total} tables total**\n\n{table}"


def search_tables(
    query: str,
    schema: str | None = None,
    limit: int = 25,
) -> str:
    """
    Search Epicor tables by name.

    Searches table names using case-insensitive substring matching.
    Results are ranked: exact matches first, then prefix matches,
    then substring matches.

    Args:
        query: Search term to match against table names (e.g. "Job", "Invoice", "Customer")
        schema: Optional schema filter (e.g. "Erp", "Ice"). If omitted, searches all schemas.
        limit: Maximum results to return (default 25)
    """
    meta = get_metadata()
    results = meta.search_tables(query, schema=schema, limit=limit)

    if not results:
        suggestions = meta.suggest_similar(query, limit=5)
        msg = f"No tables found matching '{query}'."
        if suggestions:
            msg += f"\n\nDid you mean: {', '.join(suggestions)}?"
        return msg

    # Get row counts for each result
    db = get_db()
    rows_out = []
    for t in results:
        try:
            _, count_rows = db.execute_raw(
                f"SELECT COUNT(*) FROM [{t.schema}].[{t.name}]"
            )
            row_count = str(count_rows[0][0]) if count_rows else "?"
        except Exception:
            row_count = "?"
        rows_out.append([t.schema, t.name, t.table_type, row_count])

    table = _md_table(["Schema", "Table", "Type", "Rows"], rows_out)
    return f"**{len(results)} tables matching '{query}'**\n\n{table}"


def describe_table(
    table: str,
    schema: str = "Erp",
) -> str:
    """
    Get full details about a specific Epicor table.

    Returns column definitions (name, type, nullability, keys),
    row count, table size, indexes, and related table count.

    Args:
        table: Exact table name (e.g. "JobHead", "Customer", "GLJrnDtl")
        schema: Schema name (default "Erp")
    """
    meta = get_metadata()
    info = meta.get_table(schema, table)
    if not info:
        suggestions = meta.suggest_similar(table, limit=5)
        msg = f"Table '{schema}.{table}' not found."
        if suggestions:
            msg += f"\n\nDid you mean: {', '.join(suggestions)}?"
        return msg

    db = get_db()
    parts = [f"## {info.full_name}"]

    # Row count
    try:
        _, cnt_rows = db.execute_raw(
            f"SELECT COUNT(*) FROM [{schema}].[{table}]"
        )
        row_count = cnt_rows[0][0] if cnt_rows else "?"
        parts.append(f"\n**Row count:** {row_count:,}" if isinstance(row_count, int) else f"\n**Row count:** {row_count}")
    except Exception as e:
        parts.append(f"\n**Row count:** (access denied or error: {e})")

    # Columns with types, nullability, keys
    try:
        _, col_rows = db.execute_raw(f"""
            SELECT
                c.COLUMN_NAME,
                c.DATA_TYPE,
                c.CHARACTER_MAXIMUM_LENGTH,
                c.NUMERIC_PRECISION,
                c.NUMERIC_SCALE,
                c.IS_NULLABLE,
                c.COLUMN_DEFAULT,
                CASE
                    WHEN pk.COLUMN_NAME IS NOT NULL THEN 'PK'
                    ELSE ''
                END AS KEY_TYPE
            FROM INFORMATION_SCHEMA.COLUMNS c
            LEFT JOIN (
                SELECT ku.TABLE_SCHEMA, ku.TABLE_NAME, ku.COLUMN_NAME
                FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc
                JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE ku
                    ON tc.CONSTRAINT_NAME = ku.CONSTRAINT_NAME
                    AND tc.TABLE_SCHEMA = ku.TABLE_SCHEMA
                WHERE tc.CONSTRAINT_TYPE = 'PRIMARY KEY'
            ) pk ON c.TABLE_SCHEMA = pk.TABLE_SCHEMA
                AND c.TABLE_NAME = pk.TABLE_NAME
                AND c.COLUMN_NAME = pk.COLUMN_NAME
            WHERE c.TABLE_SCHEMA = '{schema}'
                AND c.TABLE_NAME = '{table}'
            ORDER BY c.ORDINAL_POSITION
        """)

        col_table_rows = []
        for name, dtype, char_len, num_prec, num_scale, nullable, default, key in col_rows:
            # Build type string
            type_str = dtype
            if char_len and char_len > 0:
                type_str = f"{dtype}({char_len})" if char_len < 2147483647 else f"{dtype}(max)"
            elif num_prec and dtype not in ("int", "bigint", "smallint", "tinyint", "bit"):
                type_str = f"{dtype}({num_prec},{num_scale})"

            null_str = "NULL" if nullable == "YES" else "NOT NULL"
            col_table_rows.append([name, type_str, null_str, key])

        parts.append(f"\n**Columns ({len(col_table_rows)}):**\n")
        parts.append(_md_table(["Column", "Type", "Nullable", "Key"], col_table_rows))
    except Exception as e:
        parts.append(f"\n**Columns:** (error: {e})")

    # Indexes
    try:
        _, idx_rows = db.execute_raw(f"""
            SELECT
                i.name AS IndexName,
                i.type_desc AS IndexType,
                i.is_unique AS IsUnique,
                STRING_AGG(c.name, ', ') WITHIN GROUP (ORDER BY ic.key_ordinal) AS Columns
            FROM sys.indexes i
            JOIN sys.index_columns ic ON i.object_id = ic.object_id AND i.index_id = ic.index_id
            JOIN sys.columns c ON ic.object_id = c.object_id AND ic.column_id = c.column_id
            WHERE i.object_id = OBJECT_ID('{schema}.{table}')
                AND i.name IS NOT NULL
            GROUP BY i.name, i.type_desc, i.is_unique
            ORDER BY i.is_unique DESC, i.name
        """)
        if idx_rows:
            idx_table_rows = [
                [name, itype, "Yes" if unique else "No", cols]
                for name, itype, unique, cols in idx_rows
            ]
            parts.append(f"\n**Indexes ({len(idx_table_rows)}):**\n")
            parts.append(_md_table(["Index", "Type", "Unique", "Columns"], idx_table_rows))
    except Exception:
        pass  # Indexes not critical

    # Related tables (FK count)
    rels = meta.get_relationships(table, schema)
    if rels:
        parent_rels = [r for r in rels if r.parent_full == info.full_name]
        child_rels = [r for r in rels if r.child_full == info.full_name]
        rel_lines = []
        if parent_rels:
            rel_lines.append(f"References (this table has FK to): {len(parent_rels)}")
            for fk in parent_rels[:10]:
                rel_lines.append(f"  → {fk.child_full} ({fk.fk_name})")
        if child_rels:
            rel_lines.append(f"Referenced by (other tables FK to this): {len(child_rels)}")
            for fk in child_rels[:10]:
                rel_lines.append(f"  ← {fk.parent_full} ({fk.fk_name})")
        parts.append(f"\n**Relationships ({len(rels)} total):**\n")
        parts.append("\n".join(rel_lines))
    else:
        parts.append("\n**Relationships:** None (no foreign keys)")

    return "\n".join(parts)
