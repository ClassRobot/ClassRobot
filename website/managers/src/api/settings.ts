import client from './client'
import type {
  RuntimeConfigResponse,
  SettingsResponse,
  SettingsPatchPayload,
  SettingsSaveResult,
} from '@/types/api'

export function fetchSettings(): Promise<SettingsResponse> {
  return client.get('/settings').then((r) => r.data)
}

export function fetchRuntimeConfig(): Promise<RuntimeConfigResponse> {
  return client.get('/settings/runtime-config').then((r) => r.data)
}

export function patchSettings(payload: SettingsPatchPayload): Promise<SettingsSaveResult> {
  return client.patch('/settings', payload).then((r) => r.data)
}

export function rotateToken(): Promise<{
  rotated: boolean
  new_token_preview: string
  message: string
}> {
  return client.post('/settings/security/rotate-token').then((r) => r.data)
}
