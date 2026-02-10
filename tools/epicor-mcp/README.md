# Epicor MCP Server

A local MCP (Model Context Protocol) server that gives Cursor's AI agent
read-only access to the Epicor Kinetic SaaS SQL Server database.

## Prerequisites

- **uv** (Python package manager) — install from <https://astral.sh/uv>
- Credentials in the repo-root `.env` file (see below)

## Credentials

The server reads connection details from environment variables.
Place them in the repo-root `.env`:

```
EPICOR_KINETIC_READ_ONLY_SQL_SERVER_HOST=...
EPICOR_KINETIC_READ_ONLY_SQL_SERVER_PORT=...
EPICOR_KINETIC_READ_ONLY_SQL_SERVER_DATABASE=...
EPICOR_KINETIC_READ_ONLY_SQL_SERVER_USERNAME=...
EPICOR_KINETIC_READ_ONLY_SQL_SERVER_PASSWORD=...
```

## How It Works

Cursor launches this server via the config in `.cursor/mcp.json`.
The server communicates over stdio (JSON-RPC) and exposes 7 tools:

| Tool | Description |
|------|-------------|
| `query` | Run arbitrary read-only SQL (SELECT/WITH only) |
| `list_schemas` | Enumerate database schemas with table counts |
| `list_tables` | List tables in a schema with row/column counts |
| `describe_table` | Column-level detail with PK info |
| `search_columns` | Find columns by name across tables |
| `find_related_tables` | Infer relationships via naming conventions |
| `sample_data` | Preview sample rows from a table |

Plus one resource:

| Resource | Description |
|----------|-------------|
| `epicor://schema-overview` | Database overview with key characteristics |

## Running Manually

```bash
cd tools/epicor-mcp
uv run server.py
```

## Key Database Facts

- **Driver**: `pytds` (python-tds) — pymssql fails on TLS with Epicor SaaS
- **Connection**: `enc_login_only=True` is required
- **No FK constraints** on core Erp tables — relationships are application-level
- **Column naming conventions** (PartNum, CustNum, etc.) reveal relationships
- **Tables are very wide** — up to 469 columns per table
- **Connection can be flaky** — server retries with backoff automatically
