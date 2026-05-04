import client from './client'
import type { OverviewResponse } from '@/types/api'

export function fetchOverview(): Promise<OverviewResponse> {
  return client.get('/overview').then((r) => r.data)
}
