import client from './client'
import type {
  NoneBotAdapterItem,
  NoneBotAvailabilityResponse,
  NoneBotBotItem,
  NoneBotCommandItem,
  NoneBotListResponse,
  NoneBotOverviewResponse,
  NoneBotPluginItem,
} from '@/types/api'

export async function fetchNoneBotOverview(): Promise<NoneBotOverviewResponse> {
  const { data } = await client.get('/nonebot')
  return data
}

export async function fetchNoneBotPlugins(): Promise<NoneBotListResponse<NoneBotPluginItem>> {
  const { data } = await client.get('/nonebot/plugins')
  return data
}

export async function fetchNoneBotCommands(): Promise<NoneBotListResponse<NoneBotCommandItem>> {
  const { data } = await client.get('/nonebot/commands')
  return data
}

export async function fetchNoneBotAdapters(): Promise<NoneBotListResponse<NoneBotAdapterItem>> {
  const { data } = await client.get('/nonebot/adapters')
  return data
}

export async function fetchNoneBotBots(): Promise<NoneBotListResponse<NoneBotBotItem>> {
  const { data } = await client.get('/nonebot/bots')
  return data
}

export async function fetchNoneBotAvailability(): Promise<NoneBotAvailabilityResponse> {
  const { data } = await client.get('/nonebot/availability')
  return data
}

export async function updateNoneBotCommandAvailability(
  commandName: string,
  payload: { enabled: boolean; reason?: string },
): Promise<{ target: 'command'; key: string; enabled: boolean; reason: string; updated_at: string }> {
  const { data } = await client.patch(`/nonebot/commands/${encodeURIComponent(commandName)}/availability`, payload)
  return data
}

export async function updateNoneBotPluginAvailability(
  pluginModule: string,
  payload: { enabled: boolean; reason?: string },
): Promise<{ target: 'plugin'; key: string; enabled: boolean; reason: string; updated_at: string }> {
  const { data } = await client.patch(`/nonebot/plugins/${encodeURIComponent(pluginModule)}/availability`, payload)
  return data
}
