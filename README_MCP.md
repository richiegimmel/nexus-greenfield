# Epicor Database MCP Server

An MCP (Model Context Protocol) server that provides access to Epicor database table documentation and relationships through a structured API. Supports both **local** (stdio) and **network** (HTTP/SSE) transport modes.

## Features

The server provides the following tools:

### Table Information
- **search_tables**: Search Epicor database tables by name, description, or schema
- **get_table_details**: Get detailed information about a specific table (now includes relationship counts)
- **list_schemas**: List all available schemas in the Epicor database
- **get_tables_by_flag**: Filter tables by system flags or triggers

### Relationship Tools
- **get_table_relationships**: Get all relationships (parent/child) for a specific table
- **get_query_details**: Get all tables and relationships involved in a specific query
- **find_join_path**: Find possible join paths between two tables

### Database Query Tools (when DB connection is configured)
- **execute_query**: Execute read-only SQL queries against the Epicor database
- **get_table_columns**: Get column information for a table
- **get_table_stats**: Get row count and size statistics
- **list_database_schemas** / **list_database_tables**: Browse the database structure
- **get_sample_data**: Get sample rows from any table
- **test_query**: Validate a query and get estimated row count

## Installation

```bash
cd mcp-servers/epicor-db-mcp-server
npm install
npm run build
```

## Transport Modes

The server supports two transport modes:

### 1. Stdio Mode (Default - Local Use)

This is the standard MCP mode where Cursor launches the server as a child process. Used for local development on this machine.

Add to your Cursor MCP config (`~/.cursor/mcp.json`):

```json
{
  "mcpServers": {
    "epicor-database": {
      "command": "node",
      "args": ["/home/richie/app/mcp-servers/epicor-db-mcp-server/dist/index.js"],
      "env": {
        "EPICOR_CSV_PATH": "/home/richie/app/epicor-database-docs/Ice.TableAttribute.csv",
        "EPICOR_RELATIONS_CSV_PATH": "/home/richie/app/epicor-database-docs/Ice.QueryRelation.csv",
        "EPICOR_RELATION_FIELDS_CSV_PATH": "/home/richie/app/epicor-database-docs/Ice.QueryRelationField.csv",
        "DB_SERVER": "erpus-read08.epicorsaas.com",
        "DB_DATABASE": "SaaS5034_160144",
        "DB_USER": "C160144RO",
        "DB_PASSWORD": "...",
        "DB_PORT": "50127",
        "DB_ENCRYPT": "true",
        "DB_TRUST_CERT": "true"
      }
    }
  }
}
```

### 2. HTTP/SSE Mode (Network Access)

Runs as a persistent HTTP service accessible from any machine on the network. Uses Server-Sent Events (SSE) for the MCP protocol and API key authentication.

**Start manually:**

```bash
MCP_TRANSPORT=http MCP_PORT=3100 MCP_API_KEY=<your-key> node dist/index.js
```

**Or use the systemd service (recommended):**

```bash
# Install and enable
sudo cp epicor-mcp.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now epicor-mcp.service

# Check status
sudo systemctl status epicor-mcp.service

# View logs
journalctl -u epicor-mcp.service -f
```

**Connect from a remote machine** -- add to `~/.cursor/mcp.json` on the remote machine:

```json
{
  "mcpServers": {
    "epicor-database": {
      "url": "http://10.0.2.107:3100/sse?token=<your-api-key>"
    }
  }
}
```

**Health check (no auth required):**

```bash
curl http://10.0.2.107:3100/health
```

### Development

Run in development mode with auto-reload:

```bash
npm run dev
```

Build TypeScript:

```bash
npm run build
```

Watch for changes:

```bash
npm run watch
```

## Environment Variables

### Server Transport
- `MCP_TRANSPORT`: `stdio` (default) or `http`
- `MCP_PORT`: HTTP port (default: `3100`, only for http mode)
- `MCP_HOST`: Bind address (default: `0.0.0.0`, only for http mode)
- `MCP_API_KEY`: **Required** in http mode. API key for authentication.

### Epicor Documentation
- `EPICOR_CSV_PATH`: Path to the Epicor table attributes CSV file
- `EPICOR_RELATIONS_CSV_PATH`: Path to the query relations CSV file
- `EPICOR_RELATION_FIELDS_CSV_PATH`: Path to the relation fields CSV file

### Epicor Database Connection
- `DB_SERVER`: SQL Server hostname
- `DB_DATABASE`: Database name
- `DB_USER`: Database user
- `DB_PASSWORD`: Database password
- `DB_PORT`: SQL Server port (default: `1433`)
- `DB_ENCRYPT`: Enable encryption (`true`/`false`)
- `DB_TRUST_CERT`: Trust server certificate (`true`/`false`)

## Available Tools

### search_tables
Search for tables by name or description.

Parameters:
- `query` (required): Search query
- `schema` (optional): Filter by schema name
- `limit` (optional): Maximum results (default: 20)

### get_table_details
Get complete details about a specific table including relationship counts.

Parameters:
- `tableName` (required): Exact table name
- `schema` (optional): Schema name (default: "Erp")

### list_schemas
List all available database schemas.

### get_tables_by_flag
Filter tables by system flags.

Parameters:
- `systemFlag` (optional): Filter by SystemFlag
- `autoIMWriteTrigger` (optional): Filter by AutoIMWriteTrigger
- `autoIMDeleteTrigger` (optional): Filter by AutoIMDeleteTrigger
- `limit` (optional): Maximum results (default: 20)

### get_table_relationships
Get all relationships where a table is involved as parent or child.

Parameters:
- `tableName` (required): Table name to find relationships for
- `limit` (optional): Maximum results (default: 50)

### get_query_details
Get all tables and relationships involved in a specific query.

Parameters:
- `queryId` (required): The QueryID to analyze

### find_join_path
Discover possible join paths between two tables.

Parameters:
- `fromTable` (required): Starting table name
- `toTable` (required): Target table name
- `maxDepth` (optional): Maximum number of joins to traverse (default: 3)

### get_join_conditions
Get exact SQL JOIN syntax with field-level conditions between two tables.

Parameters:
- `parentTable` (required): Parent/left table name
- `childTable` (required): Child/right table name
- `queryId` (optional): Filter by specific QueryID

## License

MIT