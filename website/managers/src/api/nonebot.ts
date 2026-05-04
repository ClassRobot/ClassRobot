import client from './client'
import type {
  NoneBotAdapterItem,
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
