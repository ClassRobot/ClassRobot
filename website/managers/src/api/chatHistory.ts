import client from './client'
import type {
  ChatHistoryActorRole,
  ChatHistoryDeleteSpaceResult,
  ChatHistoryDirection,
  ChatHistoryMessageListResponse,
  ChatHistoryRecordKind,
  ChatHistorySpaceDetail,
  ChatHistorySpaceKind,
  ChatHistorySpaceListResponse,
} from '@/types/api'

export function fetchChatHistorySpaces(
  params: { kind?: ChatHistorySpaceKind; q?: string } = {},
): Promise<ChatHistorySpaceListResponse> {
  return client.get('/chat-history/spaces', { params }).then((r) => r.data)
}

export function fetchChatHistorySpaceDetail(
  kind: ChatHistorySpaceKind,
  ownerId: string,
): Promise<ChatHistorySpaceDetail> {
  return client.get(`/chat-history/spaces/${kind}/${encodeURIComponent(ownerId)}`).then((r) => r.data)
}

export function fetchChatHistoryMessages(
  kind: ChatHistorySpaceKind,
  ownerId: string,
  params: {
    q?: string
    record_kind?: ChatHistoryRecordKind | 'all'
    actor_role?: ChatHistoryActorRole | 'all'
    direction?: ChatHistoryDirection | 'all'
    message_date?: string
    page?: number
    page_size?: number
  } = {},
): Promise<ChatHistoryMessageListResponse> {
  return client.get(`/chat-history/spaces/${kind}/${encodeURIComponent(ownerId)}/messages`, { params }).then((r) => r.data)
}

export function deleteChatHistorySpace(
  kind: ChatHistorySpaceKind,
  ownerId: string,
): Promise<ChatHistoryDeleteSpaceResult> {
  return client.delete(`/chat-history/spaces/${kind}/${encodeURIComponent(ownerId)}`).then((r) => r.data)
}
