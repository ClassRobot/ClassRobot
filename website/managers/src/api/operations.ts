import client from './client'
import type {
  ActionItem,
  ActionRunResult,
  AuditLogResponse,
  TerminalCommandItem,
  TerminalRunResult,
} from '@/types/api'

export function fetchActions(): Promise<{ items: ActionItem[] }> {
  return client.get('/operations/actions').then((r) => r.data)
}

export function runAction(actionId: string): Promise<ActionRunResult> {
  return client
    .post(`/operations/actions/${encodeURIComponent(actionId)}/run`)
    .then((r) => r.data)
}

export function fetchTerminalCommands(): Promise<{ items: TerminalCommandItem[] }> {
  return client.get('/operations/terminal/commands').then((r) => r.data)
}

export function runTerminalCommand(commandId: string): Promise<TerminalRunResult> {
  return client
    .post(`/operations/terminal/commands/${encodeURIComponent(commandId)}/run`)
    .then((r) => r.data)
}

export function fetchAuditLog(params: { event_type?: string; limit?: number } = {}): Promise<AuditLogResponse> {
  return client.get('/operations/audit-log', { params }).then((r) => r.data)
}
