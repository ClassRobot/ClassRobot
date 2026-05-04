import client from './client'
import type {
  ModelConfigItem,
  ModelTestResult,
  ModelSettingsUpdateRequest,
} from '@/types/api'

export function fetchModels(): Promise<{
  items: ModelConfigItem[]
  llm_timeout: number
}> {
  return client.get('/models').then((r) => r.data)
}

export function saveModels(
  payload: ModelSettingsUpdateRequest,
): Promise<{ saved: boolean; restart_required: boolean }> {
  return client.put('/models', payload).then((r) => r.data)
}

export function testModel(name: string): Promise<ModelTestResult> {
  return client.post(`/models/${encodeURIComponent(name)}/test`).then((r) => r.data)
}
