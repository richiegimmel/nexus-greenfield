"""
Epicor metadata cache.

Loads table metadata, column info, and foreign-key relationships from
SQL Server system catalogs (INFORMATION_SCHEMA + sys.*) into memory
on first access.  Provides fast lookup methods for search, relationship
discovery, and BFS join-path finding.

Note: Ice.TableAttribute / Ice.QueryRelation are not accessible with
the read-only credentials.  We use SQL Server's own catalog instead,
which gives us real FK constraints and full schema metadata.
"""

from __future__ import annotations

import re
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from db import get_db


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class TableInfo:
    schema: str
    name: str
    table_type: str  # BASE TABLE or VIEW
    full_name: str = ""  # schema.name

    def __post_init__(self) -> None:
        self.full_name = f"{self.schema}.{self.name}"


@dataclass
class ForeignKey:
    fk_name: str
    parent_schema: str
    parent_table: str
    child_schema: str
    child_table: str
    columns: list[tuple[str, str]] = field(default_factory=list)
    # columns: list of (parent_col, child_col)

    @property
    def parent_full(self) -> str:
        return f"{self.parent_schema}.{self.parent_table}"

    @property
    def child_full(self) -> str:
        return f"{self.child_schema}.{self.child_table}"

    def join_clause(self) -> str:
        """Generate a SQL JOIN ON clause."""
        conditions = [
            f"{self.parent_table}.{pc} = {self.child_table}.{cc}"
            for pc, cc in self.columns
        ]
        return " AND ".join(conditions)


# ---------------------------------------------------------------------------
# Metadata cache
# ---------------------------------------------------------------------------

class MetadataCache:
    """
    In-memory cache of Epicor database metadata.

    Loaded once from SQL Server system catalogs on first access.
    Refreshed by restarting the MCP server process.
    """

    def __init__(self) -> None:
        self._loaded = False

        # Table lookup
        self._tables: dict[str, TableInfo] = {}  # "Schema.Table" -> TableInfo
        self._tables_by_name: dict[str, list[TableInfo]] = defaultdict(list)  # "Table" -> [TableInfo, ...]
        self._tables_by_schema: dict[str, list[TableInfo]] = defaultdict(list)

        # Foreign keys
        self._fks: list[ForeignKey] = []
        self._fks_by_parent: dict[str, list[ForeignKey]] = defaultdict(list)  # "Schema.Table" -> [FK, ...]
        self._fks_by_child: dict[str, list[ForeignKey]] = defaultdict(list)

        # Adjacency graph for BFS (undirected)
        self._adjacency: dict[str, set[str]] = defaultdict(set)

    def ensure_loaded(self) -> None:
        """Load metadata if not already loaded."""
        if not self._loaded:
            self._load()

    # -- Loading -------------------------------------------------------------

    def _load(self) -> None:
        t0 = time.monotonic()
        db = get_db()

        self._load_tables(db)
        self._load_foreign_keys(db)
        self._build_adjacency()

        elapsed = time.monotonic() - t0
        print(
            f"Metadata cache loaded: {len(self._tables)} tables, "
            f"{len(self._fks)} foreign keys in {elapsed:.1f}s",
            file=sys.stderr,
        )
        self._loaded = True

    def _load_tables(self, db: Any) -> None:
        """Load table list from INFORMATION_SCHEMA."""
        _, rows = db.execute_raw("""
            SELECT TABLE_SCHEMA, TABLE_NAME, TABLE_TYPE
            FROM INFORMATION_SCHEMA.TABLES
            ORDER BY TABLE_SCHEMA, TABLE_NAME
        """)
        for schema, name, ttype in rows:
            info = TableInfo(schema=schema, name=name, table_type=ttype)
            self._tables[info.full_name] = info
            self._tables_by_name[name].append(info)
            self._tables_by_schema[schema].append(info)

    def _load_foreign_keys(self, db: Any) -> None:
        """Load all foreign keys with their column mappings."""
        _, rows = db.execute_raw("""
            SELECT
                fk.name                                              AS FK_Name,
                OBJECT_SCHEMA_NAME(fk.parent_object_id)              AS ParentSchema,
                OBJECT_NAME(fk.parent_object_id)                     AS ParentTable,
                COL_NAME(fkc.parent_object_id, fkc.parent_column_id) AS ParentCol,
                OBJECT_SCHEMA_NAME(fk.referenced_object_id)          AS ChildSchema,
                OBJECT_NAME(fk.referenced_object_id)                 AS ChildTable,
                COL_NAME(fkc.referenced_object_id, fkc.referenced_column_id) AS ChildCol
            FROM sys.foreign_keys fk
            JOIN sys.foreign_key_columns fkc
                ON fk.object_id = fkc.constraint_object_id
            ORDER BY fk.name, fkc.constraint_column_id
        """)

        # Group by FK name
        fk_map: dict[str, ForeignKey] = {}
        for fk_name, ps, pt, pc, cs, ct, cc in rows:
            if fk_name not in fk_map:
                fk_map[fk_name] = ForeignKey(
                    fk_name=fk_name,
                    parent_schema=ps,
                    parent_table=pt,
                    child_schema=cs,
                    child_table=ct,
                )
            fk_map[fk_name].columns.append((pc, cc))

        self._fks = list(fk_map.values())
        for fk in self._fks:
            self._fks_by_parent[fk.parent_full].append(fk)
            self._fks_by_child[fk.child_full].append(fk)

    def _build_adjacency(self) -> None:
        """Build undirected adjacency graph from FK relationships."""
        for fk in self._fks:
            self._adjacency[fk.parent_full].add(fk.child_full)
            self._adjacency[fk.child_full].add(fk.parent_full)

    # -- Lookup methods ------------------------------------------------------

    def get_schemas(self) -> dict[str, int]:
        """Return {schema_name: table_count}."""
        self.ensure_loaded()
        return {s: len(ts) for s, ts in sorted(self._tables_by_schema.items())}

    def get_tables_in_schema(self, schema: str) -> list[TableInfo]:
        """Return all tables in a schema."""
        self.ensure_loaded()
        return self._tables_by_schema.get(schema, [])

    def get_table(self, schema: str, name: str) -> TableInfo | None:
        """Lookup a specific table."""
        self.ensure_loaded()
        return self._tables.get(f"{schema}.{name}")

    def resolve_table(self, name: str, schema: str | None = None) -> TableInfo | None:
        """
        Resolve a table name, optionally with schema.
        If schema is provided, does exact lookup.
        If not, tries Erp first, then any match.
        """
        self.ensure_loaded()
        if schema:
            return self._tables.get(f"{schema}.{name}")
        # Try Erp first (most common)
        erp = self._tables.get(f"Erp.{name}")
        if erp:
            return erp
        # Try any schema
        matches = self._tables_by_name.get(name, [])
        return matches[0] if matches else None

    def search_tables(self, query: str, schema: str | None = None, limit: int = 25) -> list[TableInfo]:
        """
        Search tables by name (case-insensitive substring match).
        Returns up to `limit` results, sorted by relevance
        (exact match first, then prefix, then substring).
        """
        self.ensure_loaded()
        q = query.lower()

        candidates = (
            self._tables_by_schema.get(schema, [])
            if schema
            else list(self._tables.values())
        )

        exact = []
        prefix = []
        contains = []
        for t in candidates:
            name_lower = t.name.lower()
            if name_lower == q:
                exact.append(t)
            elif name_lower.startswith(q):
                prefix.append(t)
            elif q in name_lower:
                contains.append(t)

        results = exact + sorted(prefix, key=lambda t: t.name) + sorted(contains, key=lambda t: t.name)
        return results[:limit]

    def suggest_similar(self, name: str, limit: int = 5) -> list[str]:
        """Suggest similar table names (for 'did you mean?' errors)."""
        self.ensure_loaded()
        q = name.lower()
        scored = []
        for t in self._tables.values():
            n = t.name.lower()
            # Simple scoring: shared prefix length + substring bonus
            prefix_len = 0
            for a, b in zip(q, n):
                if a == b:
                    prefix_len += 1
                else:
                    break
            sub_bonus = 2 if q in n or n in q else 0
            scored.append((prefix_len + sub_bonus, t.full_name))
        scored.sort(key=lambda x: -x[0])
        return [s[1] for s in scored[:limit] if s[0] > 0]

    # -- Relationship methods ------------------------------------------------

    def get_relationships(
        self,
        table: str,
        schema: str | None = None,
        direction: str = "both",
    ) -> list[ForeignKey]:
        """
        Get FK relationships for a table.

        direction: "parent" (table is the FK parent / referencing table),
                   "child" (table is the referenced table),
                   "both" (default).
        """
        self.ensure_loaded()
        info = self.resolve_table(table, schema)
        if not info:
            return []

        full = info.full_name
        results = []
        if direction in ("parent", "both"):
            results.extend(self._fks_by_parent.get(full, []))
        if direction in ("child", "both"):
            results.extend(self._fks_by_child.get(full, []))
        return results

    def find_join_path(
        self,
        from_table: str,
        to_table: str,
        from_schema: str | None = None,
        to_schema: str | None = None,
        max_depth: int = 3,
    ) -> list[list[str]]:
        """
        BFS to find join paths between two tables.
        Returns list of paths, each path is a list of "Schema.Table" names.
        """
        self.ensure_loaded()

        src = self.resolve_table(from_table, from_schema)
        dst = self.resolve_table(to_table, to_schema)
        if not src or not dst:
            return []

        start = src.full_name
        end = dst.full_name

        if start == end:
            return [[start]]

        # BFS
        queue: list[tuple[list[str], int]] = [([start], 0)]
        visited: set[str] = {start}
        paths: list[list[str]] = []

        while queue:
            path, depth = queue.pop(0)
            if depth >= max_depth:
                continue

            current = path[-1]
            for neighbor in self._adjacency.get(current, set()):
                if neighbor == end:
                    paths.append(path + [neighbor])
                    continue
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((path + [neighbor], depth + 1))

        return paths[:10]  # Cap at 10 paths

    def get_fk_between(self, table_a: str, table_b: str) -> list[ForeignKey]:
        """Get FK relationships directly between two tables (either direction)."""
        self.ensure_loaded()
        results = []
        for fk in self._fks:
            if (
                (fk.parent_full == table_a and fk.child_full == table_b) or
                (fk.parent_full == table_b and fk.child_full == table_a)
            ):
                results.append(fk)
        return results


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_cache: MetadataCache | None = None


def get_metadata() -> MetadataCache:
    """Get or create the singleton metadata cache."""
    global _cache
    if _cache is None:
        _cache = MetadataCache()
    return _cache
