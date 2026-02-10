"""
Data profiling tools: profile_table, profile_column.
"""

from __future__ import annotations

from typing import Any

from db import get_db
from metadata import get_metadata


def _safe_str(val: Any) -> str:
    """Convert a value to string, handling None and binary."""
    if val is None:
        return "NULL"
    if isinstance(val, bytes):
        return f"<binary {len(val)}b>"
    s = str(val)
    if len(s) > 80:
        return s[:77] + "..."
    return s


def profile_table(
    table: str,
    schema: str = "Erp",
) -> str:
    """
    Get a profiling overview of an Epicor table.

    Returns row count, and for each column: data type, null percentage,
    approximate distinct count, and a sample value.  This gives a quick
    picture of what data lives in the table and which columns are populated.

    Args:
        table: Table name (e.g. "JobHead", "Customer", "GLJrnDtl")
        schema: Schema name (default "Erp")
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

    # Row count
    try:
        _, cnt_rows = db.execute_raw(
            f"SELECT COUNT(*) FROM [{info.schema}].[{info.name}]"
        )
        total_rows = cnt_rows[0][0] if cnt_rows else 0
    except Exception as e:
        return f"**Error counting rows:** {e}"

    # Get columns
    try:
        _, col_rows = db.execute_raw(f"""
            SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = '{info.schema}' AND TABLE_NAME = '{info.name}'
            ORDER BY ORDINAL_POSITION
        """)
    except Exception as e:
        return f"**Error reading columns:** {e}"

    if not col_rows:
        return f"No columns found for {info.full_name}."

    # Skip profiling binary columns
    binary_types = {"binary", "varbinary", "image", "timestamp", "rowversion"}

    # Build a single query that profiles all columns at once
    # For large tables, use a sampled subset for distinct counts
    use_sample = total_rows > 100_000
    sample_clause = f"(SELECT TOP 50000 * FROM [{info.schema}].[{info.name}]) AS _sample" if use_sample else f"[{info.schema}].[{info.name}]"

    profile_parts = []
    col_names = []
    for col_name, dtype, nullable in col_rows:
        if dtype.lower() in binary_types:
            continue
        col_names.append((col_name, dtype))
        # For each column: null count, distinct count (approx)
        escaped = col_name.replace("'", "''")
        profile_parts.append(
            f"SUM(CASE WHEN [{col_name}] IS NULL THEN 1 ELSE 0 END) AS [{col_name}__nulls], "
            f"COUNT(DISTINCT [{col_name}]) AS [{col_name}__distinct]"
        )

    if not profile_parts:
        return f"No profilable columns in {info.full_name} (all binary/image)."

    # Execute the profiling query
    select_expr = ", ".join(profile_parts)
    profile_sql = f"SELECT {select_expr} FROM {sample_clause}"

    try:
        _, prof_rows = db.execute_raw(profile_sql)
    except Exception as e:
        return f"**Profiling query failed:** {e}\n\nTry `describe_table` for basic column info."

    prof_data = prof_rows[0] if prof_rows else ()

    # Parse results
    result_rows = []
    for i, (col_name, dtype) in enumerate(col_names):
        nulls = prof_data[i * 2] if i * 2 < len(prof_data) else "?"
        distinct = prof_data[i * 2 + 1] if i * 2 + 1 < len(prof_data) else "?"

        null_pct = ""
        if isinstance(nulls, int) and total_rows > 0:
            pct = (nulls / total_rows) * 100
            null_pct = f"{pct:.0f}%"

        distinct_str = str(distinct)
        if use_sample and isinstance(distinct, int):
            distinct_str = f"~{distinct}"

        result_rows.append([col_name, dtype, null_pct, distinct_str])

    # Get a sample value for each column (single row)
    try:
        sample_cols = ", ".join(f"[{cn}]" for cn, _ in col_names)
        _, sample_rows = db.execute_raw(
            f"SELECT TOP 1 {sample_cols} FROM [{info.schema}].[{info.name}]"
        )
        if sample_rows:
            for i, val in enumerate(sample_rows[0]):
                if i < len(result_rows):
                    result_rows[i].append(_safe_str(val))
        else:
            for r in result_rows:
                r.append("")
    except Exception:
        for r in result_rows:
            r.append("?")

    # Format output
    headers = ["Column", "Type", "Null%", "Distinct", "Sample"]
    widths = [len(h) for h in headers]
    for row in result_rows:
        for j, cell in enumerate(row):
            if j < len(widths):
                widths[j] = max(widths[j], min(len(str(cell)), 50))

    def fmt(cells: list[str]) -> str:
        return "| " + " | ".join(
            str(c)[:50].ljust(w) for c, w in zip(cells, widths)
        ) + " |"

    lines = [
        f"## Profile: {info.full_name}",
        f"**Rows:** {total_rows:,}" + (" (distinct counts sampled from 50k rows)" if use_sample else ""),
        f"**Columns:** {len(col_rows)}",
        "",
        fmt(headers),
        "| " + " | ".join("-" * w for w in widths) + " |",
    ]
    for row in result_rows:
        lines.append(fmt(row))

    return "\n".join(lines)


def profile_column(
    table: str,
    column: str,
    schema: str = "Erp",
) -> str:
    """
    Deep analysis of a single column in an Epicor table.

    Returns data type, null count/percentage, distinct count,
    min/max values, top 15 most frequent values with counts,
    and for numeric columns: average and standard deviation.

    Args:
        table: Table name (e.g. "JobHead", "Customer")
        column: Column name (e.g. "JobType", "CustNum", "Company")
        schema: Schema name (default "Erp")
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

    # Verify column exists and get its type
    try:
        _, col_meta = db.execute_raw(f"""
            SELECT DATA_TYPE, CHARACTER_MAXIMUM_LENGTH,
                   NUMERIC_PRECISION, NUMERIC_SCALE, IS_NULLABLE
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = '{info.schema}'
                AND TABLE_NAME = '{info.name}'
                AND COLUMN_NAME = '{column}'
        """)
    except Exception as e:
        return f"**Error:** {e}"

    if not col_meta:
        # List available columns
        try:
            _, avail = db.execute_raw(f"""
                SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = '{info.schema}' AND TABLE_NAME = '{info.name}'
                ORDER BY ORDINAL_POSITION
            """)
            col_list = ", ".join(r[0] for r in avail[:30])
            return (
                f"Column '{column}' not found in {info.full_name}.\n\n"
                f"Available columns: {col_list}"
                + ("..." if len(avail) > 30 else "")
            )
        except Exception:
            return f"Column '{column}' not found in {info.full_name}."

    dtype, char_len, num_prec, num_scale, nullable = col_meta[0]

    # Build type string
    type_str = dtype
    if char_len and char_len > 0:
        type_str = f"{dtype}({char_len})" if char_len < 2147483647 else f"{dtype}(max)"
    elif num_prec and dtype not in ("int", "bigint", "smallint", "tinyint", "bit"):
        type_str = f"{dtype}({num_prec},{num_scale})"

    is_numeric = dtype.lower() in (
        "int", "bigint", "smallint", "tinyint", "decimal", "numeric",
        "float", "real", "money", "smallmoney",
    )
    is_binary = dtype.lower() in ("binary", "varbinary", "image", "timestamp", "rowversion")

    parts = [
        f"## Column Profile: {info.full_name}.{column}",
        f"**Type:** {type_str}",
        f"**Nullable:** {nullable}",
    ]

    if is_binary:
        parts.append("\n(Binary column — limited profiling available)")

    # Basic stats: count, nulls, distinct, min, max
    try:
        stats_parts = [
            f"COUNT(*) AS total",
            f"SUM(CASE WHEN [{column}] IS NULL THEN 1 ELSE 0 END) AS nulls",
            f"COUNT(DISTINCT [{column}]) AS distinct_vals",
        ]
        if not is_binary:
            stats_parts.extend([
                f"MIN([{column}]) AS min_val",
                f"MAX([{column}]) AS max_val",
            ])
        if is_numeric:
            stats_parts.extend([
                f"AVG(CAST([{column}] AS FLOAT)) AS avg_val",
                f"STDEV(CAST([{column}] AS FLOAT)) AS stddev_val",
            ])

        stats_sql = f"SELECT {', '.join(stats_parts)} FROM [{info.schema}].[{info.name}]"
        _, stats_rows = db.execute_raw(stats_sql)

        if stats_rows:
            row = stats_rows[0]
            total = row[0]
            nulls = row[1]
            distinct = row[2]
            null_pct = f"{(nulls / total * 100):.1f}%" if total > 0 else "N/A"

            parts.extend([
                f"**Total rows:** {total:,}",
                f"**Null:** {nulls:,} ({null_pct})",
                f"**Distinct values:** {distinct:,}",
            ])

            idx = 3
            if not is_binary:
                min_val = _safe_str(row[idx])
                max_val = _safe_str(row[idx + 1])
                parts.extend([
                    f"**Min:** {min_val}",
                    f"**Max:** {max_val}",
                ])
                idx += 2
            if is_numeric:
                avg_val = row[idx]
                std_val = row[idx + 1]
                parts.append(f"**Avg:** {avg_val:.4f}" if avg_val is not None else "**Avg:** NULL")
                parts.append(f"**Stddev:** {std_val:.4f}" if std_val is not None else "**Stddev:** NULL")
    except Exception as e:
        parts.append(f"\n**Stats query failed:** {e}")

    # Top 15 most frequent values
    if not is_binary:
        try:
            _, freq_rows = db.execute_raw(f"""
                SELECT TOP 15 [{column}] AS val, COUNT(*) AS cnt
                FROM [{info.schema}].[{info.name}]
                GROUP BY [{column}]
                ORDER BY COUNT(*) DESC
            """)
            if freq_rows:
                parts.append(f"\n**Top {len(freq_rows)} values by frequency:**\n")
                headers = ["Value", "Count", "Pct"]
                total = sum(r[1] for r in freq_rows)
                freq_table = []
                for val, cnt in freq_rows:
                    pct = f"{(cnt / total * 100):.1f}%" if total > 0 else ""
                    freq_table.append([_safe_str(val), f"{cnt:,}", pct])

                # Render mini table
                widths = [max(len(h), max(len(r[i]) for r in freq_table)) for i, h in enumerate(headers)]
                def fmt(cells: list[str]) -> str:
                    return "| " + " | ".join(c.ljust(w) for c, w in zip(cells, widths)) + " |"

                parts.append(fmt(headers))
                parts.append("| " + " | ".join("-" * w for w in widths) + " |")
                for row in freq_table:
                    parts.append(fmt(row))
        except Exception as e:
            parts.append(f"\n**Frequency query failed:** {e}")

    return "\n".join(parts)
