import client from './client'
import type { StatusResponse, StatusCheckRequest } from '@/types/api'

export function fetchStatus(): Promise<StatusResponse> {
  return client.get('/status').then((r) => r.data)
}

export function checkStatus(targets: string[]): Promise<StatusResponse> {
  const payload: StatusCheckRequest = { targets }
  return client.post('/status/check', payload).then((r) => r.data)
}
