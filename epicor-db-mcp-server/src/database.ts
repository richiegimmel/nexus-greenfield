import sql from 'mssql';

export interface DatabaseConfig {
  server: string;
  database: string;
  user: string;
  password: string;
  port?: number;
  options?: {
    encrypt?: boolean;
    trustServerCertificate?: boolean;
    enableArithAbort?: boolean;
  };
}

export class DatabaseManager {
  private pool: sql.ConnectionPool | null = null;
  private config: sql.config;
  private connected: boolean = false;

  constructor(config: DatabaseConfig) {
    this.config = {
      server: config.server,
      database: config.database,
      user: config.user,
      password: config.password,
      port: config.port || 1433,
      options: {
        encrypt: config.options?.encrypt ?? true,
        trustServerCertificate: config.options?.trustServerCertificate ?? true,
        enableArithAbort: config.options?.enableArithAbort ?? true,
      },
      pool: {
        max: 10,
        min: 0,
        idleTimeoutMillis: 30000,
      },
      requestTimeout: 30000, // 30 second timeout
    };
  }

  async connect(): Promise<void> {
    if (this.connected && this.pool) {
      return;
    }

    try {
      this.pool = await sql.connect(this.config);
      this.connected = true;
      console.error('Database connected successfully');
    } catch (error) {
      console.error('Database connection failed:', error);
      throw error;
    }
  }

  /** Force-close the pool so the next call to connect() creates fresh TCP connections. */
  async reconnect(): Promise<void> {
    console.error('Reconnecting to database...');
    if (this.pool) {
      try { await this.pool.close(); } catch { /* ignore close errors */ }
    }
    this.pool = null;
    this.connected = false;
    await this.connect();
  }

  async disconnect(): Promise<void> {
    if (this.pool) {
      await this.pool.close();
      this.connected = false;
      this.pool = null;
    }
  }

  async executeQuery(query: string, maxRows: number = 1000): Promise<any[]> {
    if (!this.connected || !this.pool) {
      await this.connect();
    }

    // Security: Allow all read-only queries, but no modifications
    const normalizedQuery = query.trim().toUpperCase();
    const cleanQuery = normalizedQuery.replace(/^\s*(--[^\n]*\n|\/\*.*?\*\/)/gm, '').trim();

    // Block dangerous operations
    const blockedKeywords = ['INSERT', 'UPDATE', 'DELETE', 'DROP', 'CREATE', 'ALTER', 'TRUNCATE', 'EXEC XP_', 'GRANT', 'REVOKE'];
    for (const keyword of blockedKeywords) {
      if (cleanQuery.includes(keyword)) {
        throw new Error(`Query contains blocked operation: ${keyword}. Only read operations are allowed.`);
      }
    }

    // Add row limit if not present and not using TOP already
    if (!normalizedQuery.includes('TOP ') && maxRows > 0 && !normalizedQuery.startsWith('WITH')) {
      query = query.replace(/SELECT/i, `SELECT TOP ${maxRows}`);
    }

    try {
      const result = await this.pool!.request().query(query);
      return result.recordset;
    } catch (error: any) {
      // Retry once on connection-level errors (idle pool, ECONNRESET, etc.)
      const isConnectionError =
        error.code === 'ECONNRESET' ||
        error.code === 'ESOCKET' ||
        error.code === 'ECONNCLOSED' ||
        error.message?.includes('Connection lost') ||
        error.message?.includes('connection is closed');

      if (isConnectionError) {
        console.error('Connection error detected, retrying with fresh connection...');
        await this.reconnect();
        const retryResult = await this.pool!.request().query(query);
        return retryResult.recordset;
      }

      console.error('Query execution error:', error);
      throw new Error(`Query failed: ${error.message}`);
    }
  }

  async getTableColumns(schema: string, table: string): Promise<any[]> {
    const query = `
      SELECT 
        c.COLUMN_NAME,
        c.DATA_TYPE,
        c.CHARACTER_MAXIMUM_LENGTH,
        c.NUMERIC_PRECISION,
        c.NUMERIC_SCALE,
        c.IS_NULLABLE,
        c.COLUMN_DEFAULT,
        CASE 
          WHEN pk.COLUMN_NAME IS NOT NULL THEN 'PRIMARY KEY'
          WHEN fk.COLUMN_NAME IS NOT NULL THEN 'FOREIGN KEY'
          ELSE NULL
        END AS KEY_TYPE
      FROM INFORMATION_SCHEMA.COLUMNS c
      LEFT JOIN (
        SELECT ku.TABLE_SCHEMA, ku.TABLE_NAME, ku.COLUMN_NAME
        FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc
        JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE ku
          ON tc.CONSTRAINT_NAME = ku.CONSTRAINT_NAME
        WHERE tc.CONSTRAINT_TYPE = 'PRIMARY KEY'
      ) pk ON c.TABLE_SCHEMA = pk.TABLE_SCHEMA 
        AND c.TABLE_NAME = pk.TABLE_NAME 
        AND c.COLUMN_NAME = pk.COLUMN_NAME
      LEFT JOIN (
        SELECT ku.TABLE_SCHEMA, ku.TABLE_NAME, ku.COLUMN_NAME
        FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc
        JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE ku
          ON tc.CONSTRAINT_NAME = ku.CONSTRAINT_NAME
        WHERE tc.CONSTRAINT_TYPE = 'FOREIGN KEY'
      ) fk ON c.TABLE_SCHEMA = fk.TABLE_SCHEMA 
        AND c.TABLE_NAME = fk.TABLE_NAME 
        AND c.COLUMN_NAME = fk.COLUMN_NAME
      WHERE c.TABLE_SCHEMA = '${schema}' 
        AND c.TABLE_NAME = '${table}'
      ORDER BY c.ORDINAL_POSITION
    `;

    return await this.executeQuery(query, 0);
  }

  async getTableStats(schema: string, table: string): Promise<any> {
    const query = `
      SELECT 
        (SELECT COUNT(*) FROM ${schema}.${table}) AS RowCount,
        (SELECT SUM(reserved_page_count) * 8.0 / 1024 
         FROM sys.dm_db_partition_stats 
         WHERE object_id = OBJECT_ID('${schema}.${table}')) AS TableSizeMB
    `;

    const result = await this.executeQuery(query, 1);
    return result[0] || { RowCount: 0, TableSizeMB: 0 };
  }

  async listSchemas(): Promise<any[]> {
    const query = `
      SELECT DISTINCT 
        s.name AS SchemaName,
        COUNT(t.name) AS TableCount
      FROM sys.schemas s
      LEFT JOIN sys.tables t ON s.schema_id = t.schema_id
      WHERE s.name NOT IN ('sys', 'guest', 'INFORMATION_SCHEMA')
      GROUP BY s.name
      ORDER BY s.name
    `;

    return await this.executeQuery(query, 0);
  }

  async listTables(schema: string): Promise<any[]> {
    const query = `
      SELECT 
        TABLE_NAME,
        TABLE_TYPE
      FROM INFORMATION_SCHEMA.TABLES
      WHERE TABLE_SCHEMA = '${schema}'
      ORDER BY TABLE_TYPE, TABLE_NAME
    `;

    return await this.executeQuery(query, 0);
  }

  async verifyViewExists(schema: string, viewName: string): Promise<boolean> {
    const query = `
      SELECT COUNT(*) as Exists
      FROM INFORMATION_SCHEMA.VIEWS
      WHERE TABLE_SCHEMA = '${schema}'
        AND TABLE_NAME = '${viewName}'
    `;

    const result = await this.executeQuery(query, 1);
    return result[0]?.Exists > 0;
  }

  async getSampleData(schema: string, table: string, limit: number = 10): Promise<any[]> {
    const query = `SELECT TOP ${limit} * FROM ${schema}.${table}`;
    return await this.executeQuery(query, limit);
  }

  async testQuery(query: string): Promise<{ isValid: boolean; rowCount: number; error?: string }> {
    try {
      // Wrap query in count to get row count without returning all data
      const countQuery = `SELECT COUNT(*) as TotalRows FROM (${query}) AS TestQuery`;
      const result = await this.executeQuery(countQuery, 1);
      
      return {
        isValid: true,
        rowCount: result[0]?.TotalRows || 0,
      };
    } catch (error: any) {
      return {
        isValid: false,
        rowCount: 0,
        error: error.message,
      };
    }
  }
}