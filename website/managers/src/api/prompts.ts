import client from './client'
import type {
  PromptSummary,
  PromptDetail,
  PromptSaveResult,
} from '@/types/api'

export function fetchPrompts(): Promise<{ items: PromptSummary[] }> {
  return client.get('/prompts').then((r) => r.data)
}

export function fetchPrompt(name: string): Promise<PromptDetail> {
  return client.get(`/prompts/${encodeURIComponent(name)}`).then((r) => r.data)
}

export function updatePrompt(
  name: string,
  content: string,
): Promise<PromptSaveResult> {
  return client.put(`/prompts/${encodeURIComponent(name)}`, { content }).then((r) => r.data)
}

export function validatePrompt(
  name: string,
): Promise<Omit<PromptDetail, 'content'>> {
  return client.post(`/prompts/${encodeURIComponent(name)}/validate`).then((r) => r.data)
}
