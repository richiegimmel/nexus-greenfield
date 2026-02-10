#!/usr/bin/env node

import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
  McpError,
  ErrorCode
} from '@modelcontextprotocol/sdk/types.js';
import { parse } from 'csv-parse/sync';
import { readFileSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';
import { DatabaseManager, DatabaseConfig } from './database.js';
import * as dotenv from 'dotenv';

// Load environment variables from workspace root .env
// (Cursor launches MCP servers with CWD = workspace root)
const dotenvPath = process.env.DOTENV_PATH;
dotenv.config(dotenvPath ? { path: dotenvPath } : undefined);

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

interface EpicorTable {
  SchemaName: string;
  TableName: string;
  TableDesc: string;
  AutoIMWriteTrigger: string;
  AutoIMDeleteTrigger: string;
  SystemFlag: string;
  SysRevID: string;
  SysRowID: string;
  LastUpdated: string;
}

interface QueryRelation {
  Company: string;
  QueryID: string;
  SubQueryID: string;
  'Relation ID': string;
  IsFK: string;
  ParentTableID: string;
  ChildTableID: string;
  JoinType: string;
  SystemFlag: string;
  SysRevID: string;
  SysRowID: string;
}

interface QueryRelationField {
  Company: string;
  QueryID: string;
  SubQueryID: string;
  'Relation ID': string;
  Seq: string;
  Field: string;
  ParentFieldDataType: string;
  IsExpr: string;
  Field2: string;
  ChildFieldDataType: string;
  IsExpr2: string;
  AndOr: string;
  Not: string;
  '(': string;
  ')': string;
  '=': string;
  SystemFlag: string;
  SysRevID: string;
  SysRowID: string;
}

class EpicorDatabaseServer {
  private server: Server;
  private tables: EpicorTable[] = [];
  private relations: QueryRelation[] = [];
  private relationFields: QueryRelationField[] = [];
  private relationFieldsMap: Map<string, QueryRelationField[]> = new Map();
  private csvPath: string;
  private relationsCsvPath: string;
  private relationFieldsCsvPath: string;
  private dbManager: DatabaseManager | null = null;

  constructor() {
    this.server = new Server(
      {
        name: 'epicor-database-server',
        version: '1.0.0',
      },
      {
        capabilities: {
          tools: {},
        },
      }
    );

    this.csvPath = process.env.EPICOR_CSV_PATH || join(dirname(__dirname), '..', 'epicor-database-docs', 'Ice.TableAttribute.csv');
    this.relationsCsvPath = process.env.EPICOR_RELATIONS_CSV_PATH || join(dirname(__dirname), '..', 'epicor-database-docs', 'Ice.QueryRelation.csv');
    this.relationFieldsCsvPath = process.env.EPICOR_RELATION_FIELDS_CSV_PATH || join(dirname(__dirname), '..', 'epicor-database-docs', 'Ice.QueryRelationField.csv');
    
    // Initialize database manager if connection info provided.
    // Supports both SQL_SERVER_* (preferred) and DB_* (legacy) env var prefixes.
    const dbServer = process.env.SQL_SERVER_HOST || process.env.DB_SERVER;
    if (dbServer) {
      // IMPORTANT: Passwords with special chars (#, @, etc.) MUST be double-quoted
      // in .env files or dotenv will silently truncate at the '#' (comment char).
      const password = process.env.SQL_SERVER_PASSWORD || process.env.DB_PASSWORD || '';
      if (!password || password.length < 4) {
        console.error(
          'WARNING: Database password appears empty or truncated. ' +
          'If your password contains # or @, ensure it is double-quoted in .env: ' +
          'SQL_SERVER_PASSWORD="your#password"'
        );
      }

      const dbConfig: DatabaseConfig = {
        server: dbServer,
        database: process.env.SQL_SERVER_DATABASE || process.env.DB_DATABASE || 'SaaS5034_160144',
        user: process.env.SQL_SERVER_USER || process.env.DB_USER || '',
        password: password,
        port: parseInt(process.env.SQL_SERVER_PORT || process.env.DB_PORT || '1433'),
        options: {
          encrypt: true,
          trustServerCertificate: true,
        }
      };
      this.dbManager = new DatabaseManager(dbConfig);
      console.error(`Database manager initialized for ${dbServer}:${dbConfig.port}`);
    } else {
      console.error(
        'Database connection not configured - set SQL_SERVER_HOST in .env. ' +
        'Database query tools will not be available.'
      );
    }
    
    this.loadData();
    this.setupHandlers();
  }

  private loadData(): void {
    // Load table attributes
    try {
      const csvContent = readFileSync(this.csvPath, 'utf-8');
      const records = parse(csvContent, {
        columns: true,
        skip_empty_lines: true,
        bom: true,
        trim: true,
      });
      this.tables = records as EpicorTable[];
      console.error(`Loaded ${this.tables.length} Epicor tables from ${this.csvPath}`);
    } catch (error) {
      console.error(`Failed to load table CSV data: ${error}`);
      this.tables = [];
    }

    // Load query relations
    try {
      const relationsCsvContent = readFileSync(this.relationsCsvPath, 'utf-8');
      const relationsRecords = parse(relationsCsvContent, {
        columns: true,
        skip_empty_lines: true,
        bom: true,
        trim: true,
      });
      this.relations = relationsRecords as QueryRelation[];
      console.error(`Loaded ${this.relations.length} query relations from ${this.relationsCsvPath}`);
    } catch (error) {
      console.error(`Failed to load relations CSV data: ${error}`);
      this.relations = [];
    }

    // Load query relation fields
    try {
      const relationFieldsCsvContent = readFileSync(this.relationFieldsCsvPath, 'utf-8');
      
      // Custom parsing due to duplicate column names in CSV
      const lines = relationFieldsCsvContent.split('\n').filter(line => line.trim());
      const headers = lines[0].split(',').map(h => h.replace(/^\ufeff/, '').trim());
      
      this.relationFields = [];
      for (let i = 1; i < lines.length; i++) {
        const values = lines[i].split(',').map(v => v.trim());
        if (values.length >= 19) {
          this.relationFields.push({
            Company: values[0],
            QueryID: values[1],
            SubQueryID: values[2],
            'Relation ID': values[3],
            Seq: values[4],
            Field: values[5], // Parent field
            ParentFieldDataType: values[6],
            IsExpr: values[7],
            Field2: values[8], // Child field (duplicate column name in CSV)
            ChildFieldDataType: values[9],
            IsExpr2: values[10], // Child IsExpr (duplicate column name)
            AndOr: values[11],
            Not: values[12],
            '(': values[13],
            ')': values[14],
            '=': values[15],
            SystemFlag: values[16],
            SysRevID: values[17],
            SysRowID: values[18],
          });
        }
      }

      // Build a map for quick lookup by Relation ID
      this.relationFields.forEach(field => {
        const relationId = field['Relation ID'];
        if (!this.relationFieldsMap.has(relationId)) {
          this.relationFieldsMap.set(relationId, []);
        }
        this.relationFieldsMap.get(relationId)!.push(field);
      });

      console.error(`Loaded ${this.relationFields.length} query relation fields from ${this.relationFieldsCsvPath}`);
    } catch (error) {
      console.error(`Failed to load relation fields CSV data: ${error}`);
      this.relationFields = [];
    }
  }

  private setupHandlers(): void {
    this.server.setRequestHandler(ListToolsRequestSchema, async () => ({
      tools: [
        {
          name: 'search_tables',
          description: 'Search Epicor database tables by name, description, or schema',
          inputSchema: {
            type: 'object',
            properties: {
              query: {
                type: 'string',
                description: 'Search query to filter tables',
              },
              schema: {
                type: 'string',
                description: 'Filter by schema name (optional)',
              },
              limit: {
                type: 'number',
                description: 'Maximum number of results to return (default: 20)',
                default: 20,
              },
            },
            required: ['query'],
          },
        },
        {
          name: 'get_table_details',
          description: 'Get detailed information about a specific Epicor table',
          inputSchema: {
            type: 'object',
            properties: {
              tableName: {
                type: 'string',
                description: 'The exact name of the table',
              },
              schema: {
                type: 'string',
                description: 'Schema name (optional, defaults to "Erp")',
                default: 'Erp',
              },
            },
            required: ['tableName'],
          },
        },
        {
          name: 'list_schemas',
          description: 'List all available schemas in the Epicor database',
          inputSchema: {
            type: 'object',
            properties: {},
          },
        },
        {
          name: 'get_tables_by_flag',
          description: 'Get tables filtered by system flags or triggers',
          inputSchema: {
            type: 'object',
            properties: {
              systemFlag: {
                type: 'boolean',
                description: 'Filter by SystemFlag value',
              },
              autoIMWriteTrigger: {
                type: 'boolean',
                description: 'Filter by AutoIMWriteTrigger value',
              },
              autoIMDeleteTrigger: {
                type: 'boolean',
                description: 'Filter by AutoIMDeleteTrigger value',
              },
              limit: {
                type: 'number',
                description: 'Maximum number of results to return (default: 20)',
                default: 20,
              },
            },
          },
        },
        {
          name: 'get_table_relationships',
          description: 'Get all relationships for a specific table',
          inputSchema: {
            type: 'object',
            properties: {
              tableName: {
                type: 'string',
                description: 'The table name to find relationships for',
              },
              limit: {
                type: 'number',
                description: 'Maximum number of results to return (default: 50)',
                default: 50,
              },
            },
            required: ['tableName'],
          },
        },
        {
          name: 'get_query_details',
          description: 'Get all tables and relationships for a specific query',
          inputSchema: {
            type: 'object',
            properties: {
              queryId: {
                type: 'string',
                description: 'The QueryID to get details for',
              },
            },
            required: ['queryId'],
          },
        },
        {
          name: 'find_join_path',
          description: 'Find possible join paths between two tables',
          inputSchema: {
            type: 'object',
            properties: {
              fromTable: {
                type: 'string',
                description: 'Starting table name',
              },
              toTable: {
                type: 'string',
                description: 'Target table name',
              },
              maxDepth: {
                type: 'number',
                description: 'Maximum number of joins to traverse (default: 3)',
                default: 3,
              },
            },
            required: ['fromTable', 'toTable'],
          },
        },
        {
          name: 'get_join_conditions',
          description: 'Get exact SQL JOIN conditions between two tables',
          inputSchema: {
            type: 'object',
            properties: {
              parentTable: {
                type: 'string',
                description: 'Parent/left table name',
              },
              childTable: {
                type: 'string',
                description: 'Child/right table name',
              },
              queryId: {
                type: 'string',
                description: 'Optional: specific QueryID to filter by',
              },
            },
            required: ['parentTable', 'childTable'],
          },
        },
        // Database query tools (only if database is configured)
        ...(this.dbManager ? [
          {
            name: 'execute_query',
            description: 'Execute a SQL query against the Epicor database (SELECT only, max 1000 rows)',
            inputSchema: {
              type: 'object',
              properties: {
                query: {
                  type: 'string',
                  description: 'SQL SELECT query to execute',
                },
                maxRows: {
                  type: 'number',
                  description: 'Maximum rows to return (default: 1000)',
                  default: 1000,
                },
              },
              required: ['query'],
            },
          },
          {
            name: 'get_table_columns',
            description: 'Get column information for a database table',
            inputSchema: {
              type: 'object',
              properties: {
                schema: {
                  type: 'string',
                  description: 'Schema name',
                },
                table: {
                  type: 'string',
                  description: 'Table name',
                },
              },
              required: ['schema', 'table'],
            },
          },
          {
            name: 'get_table_stats',
            description: 'Get row count and size statistics for a table',
            inputSchema: {
              type: 'object',
              properties: {
                schema: {
                  type: 'string',
                  description: 'Schema name',
                },
                table: {
                  type: 'string',
                  description: 'Table name',
                },
              },
              required: ['schema', 'table'],
            },
          },
          {
            name: 'list_database_schemas',
            description: 'List all schemas in the database',
            inputSchema: {
              type: 'object',
              properties: {},
            },
          },
          {
            name: 'list_database_tables',
            description: 'List all tables in a database schema',
            inputSchema: {
              type: 'object',
              properties: {
                schema: {
                  type: 'string',
                  description: 'Schema name',
                },
              },
              required: ['schema'],
            },
          },
          {
            name: 'get_sample_data',
            description: 'Get sample rows from a table',
            inputSchema: {
              type: 'object',
              properties: {
                schema: {
                  type: 'string',
                  description: 'Schema name',
                },
                table: {
                  type: 'string',
                  description: 'Table name',
                },
                limit: {
                  type: 'number',
                  description: 'Number of rows to return (default: 10)',
                  default: 10,
                },
              },
              required: ['schema', 'table'],
            },
          },
          {
            name: 'test_query',
            description: 'Test if a query is valid and get estimated row count',
            inputSchema: {
              type: 'object',
              properties: {
                query: {
                  type: 'string',
                  description: 'SQL query to test',
                },
              },
              required: ['query'],
            },
          },
        ] : []),
      ],
    }));

    this.server.setRequestHandler(CallToolRequestSchema, async (request) => {
      const { name, arguments: args } = request.params;

      switch (name) {
        case 'search_tables':
          return this.searchTables(args);
        case 'get_table_details':
          return this.getTableDetails(args);
        case 'list_schemas':
          return this.listSchemas();
        case 'get_tables_by_flag':
          return this.getTablesByFlag(args);
        case 'get_table_relationships':
          return this.getTableRelationships(args);
        case 'get_query_details':
          return this.getQueryDetails(args);
        case 'find_join_path':
          return this.findJoinPath(args);
        case 'get_join_conditions':
          return this.getJoinConditions(args);
        // Database query tools
        case 'execute_query':
          return this.executeQuery(args);
        case 'get_table_columns':
          return this.getTableColumns(args);
        case 'get_table_stats':
          return this.getTableStats(args);
        case 'list_database_schemas':
          return this.listDatabaseSchemas();
        case 'list_database_tables':
          return this.listDatabaseTables(args);
        case 'get_sample_data':
          return this.getSampleData(args);
        case 'test_query':
          return this.testQuery(args);
        default:
          throw new McpError(
            ErrorCode.MethodNotFound,
            `Unknown tool: ${name}`
          );
      }
    });
  }

  private searchTables(args: any): any {
    const { query, schema, limit = 20 } = args;
    const queryLower = query.toLowerCase();

    let filtered = this.tables.filter(table => {
      const matchesQuery = 
        table.TableName.toLowerCase().includes(queryLower) ||
        table.TableDesc.toLowerCase().includes(queryLower);
      
      const matchesSchema = !schema || table.SchemaName === schema;
      
      return matchesQuery && matchesSchema;
    });

    filtered = filtered.slice(0, limit);

    return {
      content: [
        {
          type: 'text',
          text: `Found ${filtered.length} tables matching "${query}"${schema ? ` in schema ${schema}` : ''}:\n\n` +
            filtered.map(t => 
              `• ${t.SchemaName}.${t.TableName}: ${t.TableDesc.substring(0, 100)}${t.TableDesc.length > 100 ? '...' : ''}`
            ).join('\n'),
        },
      ],
    };
  }

  private getTableDetails(args: any): any {
    const { tableName, schema = 'Erp' } = args;
    
    const table = this.tables.find(
      t => t.TableName === tableName && t.SchemaName === schema
    );

    if (!table) {
      return {
        content: [
          {
            type: 'text',
            text: `Table ${schema}.${tableName} not found`,
          },
        ],
      };
    }

    // Count relationships for this table
    const relationships = this.relations.filter(rel => 
      rel.ParentTableID === tableName || rel.ChildTableID === tableName
    );
    const parentCount = relationships.filter(r => r.ChildTableID === tableName).length;
    const childCount = relationships.filter(r => r.ParentTableID === tableName).length;

    return {
      content: [
        {
          type: 'text',
          text: `**Table Details: ${table.SchemaName}.${table.TableName}**\n\n` +
            `**Description:**\n${table.TableDesc}\n\n` +
            `**Properties:**\n` +
            `- Schema: ${table.SchemaName}\n` +
            `- System Flag: ${table.SystemFlag}\n` +
            `- Auto IM Write Trigger: ${table.AutoIMWriteTrigger}\n` +
            `- Auto IM Delete Trigger: ${table.AutoIMDeleteTrigger}\n` +
            `- Sys Rev ID: ${table.SysRevID}\n` +
            `- Sys Row ID: ${table.SysRowID}\n` +
            `- Last Updated: ${table.LastUpdated || 'N/A'}\n\n` +
            `**Relationships:**\n` +
            `- Total: ${relationships.length} relationships\n` +
            `- Parent Tables (FKs to): ${parentCount}\n` +
            `- Child Tables (Referenced by): ${childCount}`,
        },
      ],
    };
  }

  private listSchemas(): any {
    const schemas = [...new Set(this.tables.map(t => t.SchemaName))].sort();
    
    return {
      content: [
        {
          type: 'text',
          text: `Available schemas (${schemas.length}):\n\n` +
            schemas.map(s => `• ${s}`).join('\n'),
        },
      ],
    };
  }

  private getTablesByFlag(args: any): any {
    const { systemFlag, autoIMWriteTrigger, autoIMDeleteTrigger, limit = 20 } = args;
    
    let filtered = this.tables;

    if (systemFlag !== undefined) {
      const flagValue = systemFlag ? 'TRUE' : 'FALSE';
      filtered = filtered.filter(t => t.SystemFlag === flagValue);
    }

    if (autoIMWriteTrigger !== undefined) {
      const flagValue = autoIMWriteTrigger ? 'TRUE' : 'FALSE';
      filtered = filtered.filter(t => t.AutoIMWriteTrigger === flagValue);
    }

    if (autoIMDeleteTrigger !== undefined) {
      const flagValue = autoIMDeleteTrigger ? 'TRUE' : 'FALSE';
      filtered = filtered.filter(t => t.AutoIMDeleteTrigger === flagValue);
    }

    filtered = filtered.slice(0, limit);

    const conditions = [];
    if (systemFlag !== undefined) conditions.push(`SystemFlag=${systemFlag}`);
    if (autoIMWriteTrigger !== undefined) conditions.push(`AutoIMWriteTrigger=${autoIMWriteTrigger}`);
    if (autoIMDeleteTrigger !== undefined) conditions.push(`AutoIMDeleteTrigger=${autoIMDeleteTrigger}`);

    return {
      content: [
        {
          type: 'text',
          text: `Found ${filtered.length} tables with ${conditions.join(', ')}:\n\n` +
            filtered.map(t => 
              `• ${t.SchemaName}.${t.TableName}: ${t.TableDesc.substring(0, 80)}${t.TableDesc.length > 80 ? '...' : ''}`
            ).join('\n'),
        },
      ],
    };
  }

  private getTableRelationships(args: any): any {
    const { tableName, limit = 50 } = args;
    
    const relationships = this.relations.filter(rel => 
      rel.ParentTableID === tableName || rel.ChildTableID === tableName
    ).slice(0, limit);

    const parentRels = relationships.filter(r => r.ChildTableID === tableName);
    const childRels = relationships.filter(r => r.ParentTableID === tableName);

    // Helper function to get join fields for a relation
    const getJoinFields = (relationId: string): string => {
      const fields = this.relationFieldsMap.get(relationId);
      if (!fields || fields.length === 0) return '';
      
      // Get the actual field names from the CSV columns
      const joinConditions = fields.map(f => {
        // The CSV has the parent field in the first "Field" column and child field in a duplicate column
        // We need to parse this properly from the raw records
        const parentField = f.Field;
        const childField = f.Field2 || f.Field; // Fallback if Field2 is not properly parsed
        return `${parentField} = ${childField}`;
      });
      
      return joinConditions.length > 0 ? ` [${joinConditions.join(' AND ')}]` : '';
    };

    return {
      content: [
        {
          type: 'text',
          text: `**Relationships for table: ${tableName}**\n\n` +
            `Found ${relationships.length} relationships (${parentRels.length} parent, ${childRels.length} child)\n\n` +
            (parentRels.length > 0 ? 
              `**Parent Tables (Foreign Keys to):**\n` +
              parentRels.map(r => {
                const joinFields = getJoinFields(r['Relation ID']);
                return `• ${r.ParentTableID} → ${r.ChildTableID} (${r.JoinType}, Query: ${r.QueryID})${joinFields}`;
              }).join('\n') + '\n\n' : '') +
            (childRels.length > 0 ?
              `**Child Tables (Referenced by):**\n` +
              childRels.map(r => {
                const joinFields = getJoinFields(r['Relation ID']);
                return `• ${r.ParentTableID} → ${r.ChildTableID} (${r.JoinType}, Query: ${r.QueryID})${joinFields}`;
              }).join('\n') : ''),
        },
      ],
    };
  }

  private getQueryDetails(args: any): any {
    const { queryId } = args;
    
    const queryRelations = this.relations.filter(rel => rel.QueryID === queryId);
    
    if (queryRelations.length === 0) {
      return {
        content: [
          {
            type: 'text',
            text: `No relationships found for Query ID: ${queryId}`,
          },
        ],
      };
    }

    const tables = new Set<string>();
    queryRelations.forEach(rel => {
      tables.add(rel.ParentTableID);
      tables.add(rel.ChildTableID);
    });

    // Helper function to build join condition string
    const getJoinCondition = (relationId: string): string => {
      const fields = this.relationFieldsMap.get(relationId);
      if (!fields || fields.length === 0) return '';
      
      const conditions = fields.map(f => {
        const parentField = f.Field;
        const childField = f.Field2 || f.Field;
        const operator = f['='] || '=';
        const andOr = f.AndOr || 'AND';
        const not = f.Not === 'TRUE' ? 'NOT ' : '';
        return `${not}${parentField} ${operator} ${childField}`;
      });
      
      return conditions.length > 0 ? `\n    JOIN ON: ${conditions.join(' AND ')}` : '';
    };

    return {
      content: [
        {
          type: 'text',
          text: `**Query Details: ${queryId}**\n\n` +
            `**Tables involved (${tables.size}):**\n` +
            Array.from(tables).sort().map(t => `• ${t}`).join('\n') + '\n\n' +
            `**Relationships (${queryRelations.length}):**\n` +
            queryRelations.map(r => {
              const joinCondition = getJoinCondition(r['Relation ID']);
              return `• ${r.ParentTableID} → ${r.ChildTableID} (${r.JoinType}${r.IsFK === 'TRUE' ? ', FK' : ''})${joinCondition}`;
            }).join('\n'),
        },
      ],
    };
  }

  private findJoinPath(args: any): any {
    const { fromTable, toTable, maxDepth = 3 } = args;
    
    if (fromTable === toTable) {
      return {
        content: [
          {
            type: 'text',
            text: `Tables are the same: ${fromTable}`,
          },
        ],
      };
    }

    // Build adjacency list for graph traversal
    const graph = new Map<string, Set<string>>();
    this.relations.forEach(rel => {
      if (!graph.has(rel.ParentTableID)) {
        graph.set(rel.ParentTableID, new Set());
      }
      if (!graph.has(rel.ChildTableID)) {
        graph.set(rel.ChildTableID, new Set());
      }
      graph.get(rel.ParentTableID)!.add(rel.ChildTableID);
      graph.get(rel.ChildTableID)!.add(rel.ParentTableID);
    });

    // BFS to find shortest path
    const queue: Array<{table: string, path: string[], depth: number}> = [
      {table: fromTable, path: [fromTable], depth: 0}
    ];
    const visited = new Set<string>([fromTable]);
    const paths: string[][] = [];

    while (queue.length > 0) {
      const {table, path, depth} = queue.shift()!;
      
      if (depth > maxDepth) continue;
      
      if (table === toTable) {
        paths.push(path);
        continue;
      }

      const neighbors = graph.get(table);
      if (neighbors) {
        for (const neighbor of neighbors) {
          if (!visited.has(neighbor) || neighbor === toTable) {
            visited.add(neighbor);
            queue.push({
              table: neighbor,
              path: [...path, neighbor],
              depth: depth + 1
            });
          }
        }
      }
    }

    if (paths.length === 0) {
      return {
        content: [
          {
            type: 'text',
            text: `No join path found between ${fromTable} and ${toTable} within ${maxDepth} joins`,
          },
        ],
      };
    }

    return {
      content: [
        {
          type: 'text',
          text: `**Join paths from ${fromTable} to ${toTable}:**\n\n` +
            paths.slice(0, 5).map((path, i) => 
              `Path ${i + 1} (${path.length - 1} joins):\n` +
              path.join(' → ')
            ).join('\n\n') +
            (paths.length > 5 ? `\n\n...and ${paths.length - 5} more paths` : ''),
        },
      ],
    };
  }

  private getJoinConditions(args: any): any {
    const { parentTable, childTable, queryId } = args;
    
    // Find all relations between these two tables
    let relations = this.relations.filter(rel => 
      rel.ParentTableID === parentTable && rel.ChildTableID === childTable
    );
    
    // Optionally filter by queryId
    if (queryId) {
      relations = relations.filter(rel => rel.QueryID === queryId);
    }
    
    if (relations.length === 0) {
      return {
        content: [
          {
            type: 'text',
            text: `No direct relationship found between ${parentTable} and ${childTable}${queryId ? ` in query ${queryId}` : ''}`,
          },
        ],
      };
    }
    
    // Build detailed join conditions for each relation
    const joinDetails = relations.map(rel => {
      const fields = this.relationFieldsMap.get(rel['Relation ID']) || [];
      
      if (fields.length === 0) {
        return {
          queryId: rel.QueryID,
          joinType: rel.JoinType,
          isFK: rel.IsFK === 'TRUE',
          conditions: 'No field mappings available',
          sql: `-- No field mappings found for this relationship`,
        };
      }
      
      // Build SQL JOIN clause
      const conditions = fields.map(f => {
        const parentField = f.Field;
        const childField = f.Field2 || f.Field;
        const operator = f['='] || '=';
        const not = f.Not === 'TRUE' ? 'NOT ' : '';
        return `${not}${parentTable}.${parentField} ${operator} ${childTable}.${childField}`;
      });
      
      const joinKeyword = rel.JoinType === 'Inner' ? 'INNER JOIN' : 
                          rel.JoinType === 'LeftOuter' ? 'LEFT OUTER JOIN' :
                          rel.JoinType === 'RightOuter' ? 'RIGHT OUTER JOIN' :
                          'JOIN';
      
      const sql = `${joinKeyword} ${childTable} ON ${conditions.join(' AND ')}`;
      
      return {
        queryId: rel.QueryID,
        joinType: rel.JoinType,
        isFK: rel.IsFK === 'TRUE',
        conditions: conditions.join(' AND '),
        sql: sql,
      };
    });
    
    return {
      content: [
        {
          type: 'text',
          text: `**JOIN Conditions: ${parentTable} → ${childTable}**\n\n` +
            `Found ${relations.length} relationship(s):\n\n` +
            joinDetails.map((jd, i) => 
              `**${i + 1}. Query: ${jd.queryId}**\n` +
              `- Type: ${jd.joinType}${jd.isFK ? ' (Foreign Key)' : ''}\n` +
              `- Condition: ${jd.conditions}\n` +
              `- SQL: \`${jd.sql}\`\n`
            ).join('\n'),
        },
      ],
    };
  }

  // Database query methods
  private async executeQuery(args: any): Promise<any> {
    if (!this.dbManager) {
      throw new McpError(
        ErrorCode.InvalidRequest,
        'Database connection not configured'
      );
    }

    const { query, maxRows = 1000 } = args;
    
    try {
      const results = await this.dbManager.executeQuery(query, maxRows);
      
      return {
        content: [
          {
            type: 'text',
            text: `Query executed successfully. Returned ${results.length} rows.\n\n` +
              `\`\`\`json\n${JSON.stringify(results, null, 2)}\n\`\`\``,
          },
        ],
      };
    } catch (error: any) {
      return {
        content: [
          {
            type: 'text',
            text: `Query execution failed: ${error.message}`,
          },
        ],
      };
    }
  }

  private async getTableColumns(args: any): Promise<any> {
    if (!this.dbManager) {
      throw new McpError(
        ErrorCode.InvalidRequest,
        'Database connection not configured'
      );
    }

    const { schema, table } = args;
    
    try {
      const columns = await this.dbManager.getTableColumns(schema, table);
      
      return {
        content: [
          {
            type: 'text',
            text: `**Columns for ${schema}.${table}:**\n\n` +
              columns.map((col: any) => 
                `- **${col.COLUMN_NAME}** (${col.DATA_TYPE}` +
                `${col.CHARACTER_MAXIMUM_LENGTH ? `(${col.CHARACTER_MAXIMUM_LENGTH})` : ''}` +
                `${col.NUMERIC_PRECISION ? `(${col.NUMERIC_PRECISION},${col.NUMERIC_SCALE})` : ''}` +
                `) ${col.IS_NULLABLE === 'YES' ? 'NULL' : 'NOT NULL'}` +
                `${col.KEY_TYPE ? ` [${col.KEY_TYPE}]` : ''}`
              ).join('\n'),
          },
        ],
      };
    } catch (error: any) {
      return {
        content: [
          {
            type: 'text',
            text: `Failed to get table columns: ${error.message}`,
          },
        ],
      };
    }
  }

  private async getTableStats(args: any): Promise<any> {
    if (!this.dbManager) {
      throw new McpError(
        ErrorCode.InvalidRequest,
        'Database connection not configured'
      );
    }

    const { schema, table } = args;
    
    try {
      const stats = await this.dbManager.getTableStats(schema, table);
      
      return {
        content: [
          {
            type: 'text',
            text: `**Statistics for ${schema}.${table}:**\n\n` +
              `- Row Count: ${stats.RowCount || 0}\n` +
              `- Table Size: ${(stats.TableSizeMB || 0).toFixed(2)} MB`,
          },
        ],
      };
    } catch (error: any) {
      return {
        content: [
          {
            type: 'text',
            text: `Failed to get table statistics: ${error.message}`,
          },
        ],
      };
    }
  }

  private async listDatabaseSchemas(): Promise<any> {
    if (!this.dbManager) {
      throw new McpError(
        ErrorCode.InvalidRequest,
        'Database connection not configured'
      );
    }
    
    try {
      const schemas = await this.dbManager.listSchemas();
      
      return {
        content: [
          {
            type: 'text',
            text: `**Database Schemas:**\n\n` +
              schemas.map((s: any) => 
                `- **${s.SchemaName}** (${s.TableCount} tables)`
              ).join('\n'),
          },
        ],
      };
    } catch (error: any) {
      return {
        content: [
          {
            type: 'text',
            text: `Failed to list schemas: ${error.message}`,
          },
        ],
      };
    }
  }

  private async listDatabaseTables(args: any): Promise<any> {
    if (!this.dbManager) {
      throw new McpError(
        ErrorCode.InvalidRequest,
        'Database connection not configured'
      );
    }

    const { schema } = args;
    
    try {
      const tables = await this.dbManager.listTables(schema);
      
      return {
        content: [
          {
            type: 'text',
            text: `**Tables in schema ${schema}:**\n\n` +
              tables.map((t: any) => 
                `- ${t.TABLE_NAME} (${t.TABLE_TYPE})`
              ).join('\n'),
          },
        ],
      };
    } catch (error: any) {
      return {
        content: [
          {
            type: 'text',
            text: `Failed to list tables: ${error.message}`,
          },
        ],
      };
    }
  }

  private async getSampleData(args: any): Promise<any> {
    if (!this.dbManager) {
      throw new McpError(
        ErrorCode.InvalidRequest,
        'Database connection not configured'
      );
    }

    const { schema, table, limit = 10 } = args;
    
    try {
      const data = await this.dbManager.getSampleData(schema, table, limit);
      
      return {
        content: [
          {
            type: 'text',
            text: `**Sample data from ${schema}.${table} (${data.length} rows):**\n\n` +
              `\`\`\`json\n${JSON.stringify(data, null, 2)}\n\`\`\``,
          },
        ],
      };
    } catch (error: any) {
      return {
        content: [
          {
            type: 'text',
            text: `Failed to get sample data: ${error.message}`,
          },
        ],
      };
    }
  }

  private async testQuery(args: any): Promise<any> {
    if (!this.dbManager) {
      throw new McpError(
        ErrorCode.InvalidRequest,
        'Database connection not configured'
      );
    }

    const { query } = args;
    
    try {
      const result = await this.dbManager.testQuery(query);
      
      return {
        content: [
          {
            type: 'text',
            text: `**Query Test Results:**\n\n` +
              `- Valid: ${result.isValid ? 'Yes ✓' : 'No ✗'}\n` +
              `- Estimated Row Count: ${result.rowCount}\n` +
              (result.error ? `- Error: ${result.error}` : ''),
          },
        ],
      };
    } catch (error: any) {
      return {
        content: [
          {
            type: 'text',
            text: `Failed to test query: ${error.message}`,
          },
        ],
      };
    }
  }

  async run(): Promise<void> {
    const transport = new StdioServerTransport();
    await this.server.connect(transport);
    console.error('Epicor Database MCP server running');
  }
}

const server = new EpicorDatabaseServer();
server.run().catch(console.error);