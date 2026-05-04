import client from './client'
import type { LogFileItem, LogReadResult } from '@/types/api'

export function fetchLogs(): Promise<{ items: LogFileItem[] }> {
  return client.get('/logs').then((r) => r.data)
}

export function readLog(
  path: string,
  offset = 0,
  limit = 500,
): Promise<LogReadResult> {
  return client
    .get('/logs/read', { params: { path, offset, limit } })
    .then((r) => r.data)
}

export function tailLog(path: string, lines = 300): Promise<LogReadResult> {
  return client
    .get('/logs/tail', { params: { path, lines } })
    .then((r) => r.data)
}
