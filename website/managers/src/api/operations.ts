import client from './client'
import type {
  ActionItem,
  ActionRunResult,
  AutomationScriptItem,
  AutomationScriptPayload,
  AuditLogResponse,
  TerminalCommandItem,
  TerminalExecuteRequest,
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

export function executeTerminalCommand(payload: TerminalExecuteRequest): Promise<TerminalRunResult> {
  return client.post('/operations/terminal/run', payload).then((r) => r.data)
}

export function fetchAutomationScripts(): Promise<{ items: AutomationScriptItem[]; total: number; path: string }> {
  return client.get('/operations/scripts').then((r) => r.data)
}

export function createAutomationScript(payload: AutomationScriptPayload): Promise<AutomationScriptItem> {
  return client.post('/operations/scripts', payload).then((r) => r.data)
}

export function updateAutomationScript(
  scriptId: string,
  payload: Partial<AutomationScriptPayload>,
): Promise<AutomationScriptItem> {
  return client.patch(`/operations/scripts/${encodeURIComponent(scriptId)}`, payload).then((r) => r.data)
}

export function deleteAutomationScript(scriptId: string): Promise<{ deleted: boolean; id: string }> {
  return client.delete(`/operations/scripts/${encodeURIComponent(scriptId)}`).then((r) => r.data)
}

export function runAutomationScript(scriptId: string): Promise<TerminalRunResult> {
  return client.post(`/operations/scripts/${encodeURIComponent(scriptId)}/run`).then((r) => r.data)
}

export function fetchAuditLog(params: { event_type?: string; limit?: number } = {}): Promise<AuditLogResponse> {
  return client.get('/operations/audit-log', { params }).then((r) => r.data)
}
