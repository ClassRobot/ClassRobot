import client from './client'
import type { SkillSummary, SkillDetail, SkillReloadResult } from '@/types/api'

export function fetchSkills(): Promise<{ items: SkillSummary[] }> {
  return client.get('/skills').then((r) => r.data)
}

export function fetchSkill(name: string): Promise<SkillDetail> {
  return client.get(`/skills/${encodeURIComponent(name)}`).then((r) => r.data)
}

export function reloadSkills(): Promise<SkillReloadResult> {
  return client.post('/skills/reload').then((r) => r.data)
}
