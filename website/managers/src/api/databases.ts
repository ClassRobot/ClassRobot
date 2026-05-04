import client from './client'
import type {
  DatabaseConnectionResponse,
  DatabaseRowUpdateRequest,
  DatabaseRowUpdateResponse,
  DatabaseSchemaResponse,
  DatabaseTableListResponse,
  DatabaseTableRowsResponse,
} from '@/types/api'

export async function fetchDatabases(): Promise<DatabaseConnectionResponse> {
  const { data } = await client.get('/databases')
  return data
}

export async function fetchDatabaseSchema(databaseId: string, schema?: string): Promise<DatabaseSchemaResponse> {
  const { data } = await client.get(`/databases/${databaseId}/schema`, { params: { schema } })
  return data
}

export async function fetchDatabaseTables(databaseId: string, schema?: string): Promise<DatabaseTableListResponse> {
  const { data } = await client.get(`/databases/${databaseId}/tables`, { params: { schema } })
  return data
}

export async function fetchTableRows(
  databaseId: string,
  tableName: string,
  params: { schema?: string; page?: number; page_size?: number } = {},
): Promise<DatabaseTableRowsResponse> {
  const { data } = await client.get(`/databases/${databaseId}/tables/${encodeURIComponent(tableName)}/rows`, {
    params,
  })
  return data
}

export async function updateTableRow(
  databaseId: string,
  tableName: string,
  payload: DatabaseRowUpdateRequest,
  schema?: string,
): Promise<DatabaseRowUpdateResponse> {
  const { data } = await client.patch(
    `/databases/${databaseId}/tables/${encodeURIComponent(tableName)}/rows`,
    payload,
    { params: { schema } },
  )
  return data
}
