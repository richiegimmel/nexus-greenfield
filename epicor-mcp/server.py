#!/usr/bin/env python3
"""
Epicor Database MCP Server.

Provides AI agents with comprehensive read-only access to the Epicor
Kinetic SQL Server database for schema exploration, data profiling,
relationship discovery, and ad-hoc querying.

Transport: stdio (standard for Cursor IDE integration)
"""

from __future__ import annotations

import sys
import os

# Ensure the epicor-mcp directory is on sys.path so local imports work
# regardless of how Cursor launches the process.
_this_dir = os.path.dirname(os.path.abspath(__file__))
if _this_dir not in sys.path:
    sys.path.insert(0, _this_dir)

from mcp.server.fastmcp import FastMCP

# ---------------------------------------------------------------------------
# Create the FastMCP server instance
# ---------------------------------------------------------------------------

mcp = FastMCP(
    "epicor-db",
    instructions=(
        "Epicor Kinetic database explorer (read-only). "
        "Use these tools to explore the Epicor ERP schema, "
        "understand table relationships, profile data, and run "
        "ad-hoc SELECT queries. All data is from Atlas Machine & Supply's "
        "production Epicor instance (company 160144). "
        "Start with list_schemas or search_tables to discover tables, "
        "then use describe_table or sample_data to dig in."
    ),
)

# ---------------------------------------------------------------------------
# Register tools from tool modules
# ---------------------------------------------------------------------------

# Schema discovery
from tools.schema import list_schemas, search_tables, describe_table

mcp.tool()(list_schemas)
mcp.tool()(search_tables)
mcp.tool()(describe_table)

# Relationship discovery
from tools.relationships import find_relationships, find_join_path

mcp.tool()(find_relationships)
mcp.tool()(find_join_path)

# Data querying
from tools.query import execute_query, sample_data

mcp.tool()(execute_query)
mcp.tool()(sample_data)

# Data profiling
from tools.profiling import profile_table, profile_column

mcp.tool()(profile_table)
mcp.tool()(profile_column)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Start the MCP server on stdio transport."""
    print("Starting Epicor DB MCP server (stdio)...", file=sys.stderr)

    # Eagerly initialize DB connection and metadata cache on startup
    # so we fail fast if credentials are wrong.
    from db import get_db
    from metadata import get_metadata

    try:
        db = get_db()
        print("DB connection: OK", file=sys.stderr)
    except Exception as exc:
        print(f"FATAL: DB connection failed: {exc}", file=sys.stderr)
        sys.exit(1)

    try:
        meta = get_metadata()
        meta.ensure_loaded()
        print("Metadata cache: OK", file=sys.stderr)
    except Exception as exc:
        print(f"WARNING: Metadata cache failed: {exc}", file=sys.stderr)
        # Don't exit — tools can still work without the cache

    # Run the MCP server
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
