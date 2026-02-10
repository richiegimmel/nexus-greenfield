# Epicor Database MCP Server

Read-only MCP server for exploring the Epicor Kinetic SQL Server database.
Used by AI agents in Cursor to understand Epicor's schema, data, and
relationships — informing Nexus schema design and data migration planning.

## Tools (9)

| Tool | Purpose |
|------|---------|
| `list_schemas` | List all database schemas with table counts |
| `search_tables` | Search tables by name (substring match, ranked) |
| `describe_table` | Full table details: columns, types, keys, indexes, relationships |
| `find_relationships` | FK relationships for a table (parent/child, with join conditions) |
| `find_join_path` | BFS pathfinding between two tables via FK relationships |
| `execute_query` | Run arbitrary read-only SQL (SELECT only, with row limits) |
| `sample_data` | Smart sample rows (excludes binary cols, truncates strings) |
| `profile_table` | Table overview: row count + per-column null%, distinct count, sample |
| `profile_column` | Deep column analysis: min/max, frequency, avg/stddev for numerics |

## Setup

The server is already configured in `.cursor/mcp.json`. It uses the project
`.venv` and reads credentials from the workspace root `.env`.

Dependencies (already installed in `.venv`):
- `mcp` — Official MCP Python SDK
- `python-tds` — Pure Python SQL Server driver

## Architecture

- **Transport:** stdio (standard for Cursor MCP servers)
- **Connection:** Eager connect on startup, auto-reconnect on errors
- **Metadata:** Table list + FK relationships cached in memory on startup (~0.4s)
- **Safety:** Write operations blocked at the MCP layer; DB credentials are read-only
- **No rate limiting:** Designed for maximum query speed

## Known Limitations

- **Epicor has very few formal FK constraints** (~352 total, ~180 in Erp).
  Most table relationships use naming conventions (e.g., Company + JobNum)
  rather than FK constraints. `find_relationships` and `find_join_path`
  only work with actual FK constraints. For conventionally-linked tables
  (like JobHead → JobMtl), use `describe_table` to see column names and
  construct joins manually.
- **`Ice` schema data tables are not accessible** with the read-only
  credentials (Ice.TableAttribute, Ice.QueryRelation, etc.). Metadata
  comes from SQL Server system catalogs instead.
