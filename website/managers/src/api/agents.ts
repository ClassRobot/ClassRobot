import client from './client'
import type {
  PaginatedResponse,
  AgentRunSummary,
  AgentRunDetail,
  AgentCheckpointSummary,
  AgentCheckpointDetail,
} from '@/types/api'

export interface AgentListParams {
  status?: string
  kind?: string
  q?: string
  page?: number
  page_size?: number
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
