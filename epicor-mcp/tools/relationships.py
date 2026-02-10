"""
Relationship discovery tools: find_relationships, find_join_path.
"""

from __future__ import annotations

from metadata import get_metadata


def find_relationships(
    table: str,
    schema: str | None = None,
    direction: str = "both",
    limit: int = 50,
) -> str:
    """
    Get all foreign-key relationships for an Epicor table.

    Shows parent/child FK relationships including the exact join columns.
    Use this to understand how a table connects to other tables.

    Args:
        table: Table name (e.g. "JobHead", "InvcHead", "Customer")
        schema: Schema name (default: auto-detect, tries Erp first)
        direction: "both" (default), "parent" (this table references others),
                   or "child" (other tables reference this one)
        limit: Maximum relationships to return (default 50)
    """
    meta = get_metadata()
    info = meta.resolve_table(table, schema)
    if not info:
        suggestions = meta.suggest_similar(table, limit=5)
        msg = f"Table '{table}' not found."
        if suggestions:
            msg += f"\n\nDid you mean: {', '.join(suggestions)}?"
        return msg

    rels = meta.get_relationships(table, schema=info.schema, direction=direction)

    if not rels:
        return f"No foreign-key relationships found for {info.full_name} (direction={direction})."

    rels = rels[:limit]

    lines = [f"**{len(rels)} relationships for {info.full_name}** (direction={direction})\n"]

    # Group by direction
    outgoing = [r for r in rels if r.parent_full == info.full_name]
    incoming = [r for r in rels if r.child_full == info.full_name]

    if outgoing:
        lines.append(f"### References (this table → other tables): {len(outgoing)}\n")
        for fk in outgoing:
            col_pairs = ", ".join(f"{pc}={cc}" for pc, cc in fk.columns)
            lines.append(
                f"- **→ {fk.child_full}** "
                f"(`{fk.fk_name}`)\n"
                f"  JOIN ON: {fk.join_clause()}\n"
            )

    if incoming:
        lines.append(f"### Referenced by (other tables → this table): {len(incoming)}\n")
        for fk in incoming:
            lines.append(
                f"- **← {fk.parent_full}** "
                f"(`{fk.fk_name}`)\n"
                f"  JOIN ON: {fk.join_clause()}\n"
            )

    return "\n".join(lines)


def find_join_path(
    from_table: str,
    to_table: str,
    from_schema: str | None = None,
    to_schema: str | None = None,
    max_depth: int = 3,
) -> str:
    """
    Find how to join two Epicor tables through FK relationships.

    Uses BFS to find the shortest path(s) between two tables via
    foreign-key relationships. Returns the path and join conditions
    at each hop.

    Args:
        from_table: Starting table name (e.g. "JobHead")
        to_table: Target table name (e.g. "Customer")
        from_schema: Schema for from_table (default: auto-detect)
        to_schema: Schema for to_table (default: auto-detect)
        max_depth: Maximum number of joins to traverse (default 3)
    """
    meta = get_metadata()

    src = meta.resolve_table(from_table, from_schema)
    dst = meta.resolve_table(to_table, to_schema)

    errors = []
    if not src:
        suggestions = meta.suggest_similar(from_table, limit=3)
        msg = f"Table '{from_table}' not found."
        if suggestions:
            msg += f" Did you mean: {', '.join(suggestions)}?"
        errors.append(msg)
    if not dst:
        suggestions = meta.suggest_similar(to_table, limit=3)
        msg = f"Table '{to_table}' not found."
        if suggestions:
            msg += f" Did you mean: {', '.join(suggestions)}?"
        errors.append(msg)
    if errors:
        return "\n".join(errors)

    paths = meta.find_join_path(
        from_table, to_table,
        from_schema=src.schema if src else None,
        to_schema=dst.schema if dst else None,
        max_depth=max_depth,
    )

    if not paths:
        return (
            f"No join path found between {src.full_name} and {dst.full_name} "
            f"within {max_depth} hops.\n\n"
            f"Try increasing max_depth, or the tables may not be connected "
            f"via foreign keys."
        )

    lines = [
        f"**{len(paths)} join path(s) from {src.full_name} → {dst.full_name}**\n"
    ]

    for i, path in enumerate(paths):
        lines.append(f"### Path {i + 1} ({len(path) - 1} join{'s' if len(path) > 2 else ''})\n")
        lines.append(f"**Route:** {' → '.join(path)}\n")

        # Show join conditions for each hop
        for j in range(len(path) - 1):
            a, b = path[j], path[j + 1]
            fks = meta.get_fk_between(a, b)
            if fks:
                for fk in fks:
                    lines.append(
                        f"**{fk.parent_table} → {fk.child_table}:**\n"
                        f"```sql\n"
                        f"JOIN {fk.child_full} ON {fk.join_clause()}\n"
                        f"```\n"
                    )
            else:
                lines.append(f"({a} ↔ {b}: no direct FK found — check manually)\n")

    return "\n".join(lines)
