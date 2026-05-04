import client from './client'
import type { ActionItem, ActionRunResult } from '@/types/api'

export function fetchActions(): Promise<{ items: ActionItem[] }> {
  return client.get('/operations/actions').then((r) => r.data)
}

export function runAction(actionId: string): Promise<ActionRunResult> {
  return client
    .post(`/operations/actions/${encodeURIComponent(actionId)}/run`)
    .then((r) => r.data)
}
