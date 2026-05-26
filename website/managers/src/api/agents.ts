import client from './client'
import type {
  PaginatedResponse,
  AgentDesignerResponse,
  AgentDesignerSaveResponse,
  AgentOverviewResponse,
  AgentRunSummary,
  AgentRunDetail,
  AgentCheckpointSummary,
  AgentCheckpointDetail,
  AgentLiveTraceDetail,
  AgentLiveTraceListResponse,
  AgentLiveTraceStatus,
} from '@/types/api'

export interface AgentListParams {
  status?: string
  kind?: string
  q?: string
  page?: number
  page_size?: number
}

export function fetchAgentOverview(): Promise<AgentOverviewResponse> {
  return client.get('/agents/overview').then((r) => r.data)
}

export function fetchAgentDesigner(): Promise<AgentDesignerResponse> {
  return client.get('/agents/designer').then((r) => r.data)
}

export function saveAgentDesigner(payload: {
  nodes: AgentDesignerResponse['draft']['nodes']
  edges: AgentDesignerResponse['draft']['edges']
  note?: string
  apply_to_runtime?: boolean
}): Promise<AgentDesignerSaveResponse> {
  return client.put('/agents/designer', payload).then((r) => r.data)
}

export function fetchAgentRuns(
  params: AgentListParams = {},
): Promise<PaginatedResponse<AgentRunSummary>> {
  return client.get('/agents/runs', { params }).then((r) => r.data)
}

export function fetchAgentRun(traceId: string): Promise<AgentRunDetail> {
  return client.get(`/agents/runs/${encodeURIComponent(traceId)}`).then((r) => r.data)
}

export function fetchAgentCheckpoints(
  params: { status?: string; page?: number; page_size?: number } = {},
): Promise<PaginatedResponse<AgentCheckpointSummary>> {
  return client.get('/agents/checkpoints', { params }).then((r) => r.data)
}

export function fetchAgentCheckpoint(
  userId: number,
): Promise<AgentCheckpointDetail> {
  return client.get(`/agents/checkpoints/${userId}`).then((r) => r.data)
}

export function deleteAgentCheckpoint(
  userId: number,
): Promise<{ deleted: boolean; user_id: number }> {
  return client.delete(`/agents/checkpoints/${userId}`).then((r) => r.data)
}

export function fetchAgentLiveTraceStatus(): Promise<AgentLiveTraceStatus> {
  return client.get('/agents/live/status').then((r) => r.data)
}

export function fetchAgentLiveTraces(): Promise<AgentLiveTraceListResponse> {
  return client.get('/agents/live/traces').then((r) => r.data)
}

export function fetchAgentLiveTrace(traceId: string): Promise<AgentLiveTraceDetail> {
  return client.get(`/agents/live/traces/${encodeURIComponent(traceId)}`).then((r) => r.data)
}
