# Epicor Database MCP Server

An MCP (Model Context Protocol) server that provides access to Epicor database table documentation and relationships through a structured API.

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

## Installation

```bash
cd mcp-servers/epicor-db-mcp-server
npm install
npm run build
```

## Usage

### With Claude Desktop

Add to your Claude Desktop configuration (`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS):

```json
{
  "mcpServers": {
    "epicor-database": {
      "command": "node",
      "args": ["/home/richie/app/mcp-servers/epicor-db-mcp-server/dist/index.js"],
      "env": {
        "EPICOR_CSV_PATH": "/home/richie/app/epicor-database-docs/epicor_table_attributes.csv",
        "EPICOR_RELATIONS_CSV_PATH": "/home/richie/app/epicor-database-docs/Ice.QueryRelation.csv"
      }
    }
  }
}
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

- `EPICOR_CSV_PATH`: Path to the Epicor table attributes CSV file (defaults to `../epicor-database-docs/Ice.TableAttribute.csv`)
- `EPICOR_RELATIONS_CSV_PATH`: Path to the query relations CSV file (defaults to `../epicor-database-docs/Ice.QueryRelation.csv`)
- `EPICOR_RELATION_FIELDS_CSV_PATH`: Path to the relation fields CSV file (defaults to `../epicor-database-docs/Ice.QueryRelationField.csv`)

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