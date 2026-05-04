import client from './client'
import type { IntegrationsResponse } from '@/types/api'

export function fetchIntegrations(): Promise<IntegrationsResponse> {
  return client.get('/integrations').then((r) => r.data)
}
