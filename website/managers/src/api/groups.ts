import client from './client'
import type {
  GroupDetail,
  GroupSummary,
  PaginatedResponse,
} from '@/types/api'

export interface GroupListParams {
  q?: string
  platform_id?: string
  join_method?: string
  page?: number
  page_size?: number
}

export function fetchGroups(params: GroupListParams = {}): Promise<PaginatedResponse<GroupSummary>> {
  return client.get('/groups', { params }).then((r) => r.data)
}

export function fetchGroupDetail(groupId: number): Promise<GroupDetail> {
  return client.get(`/groups/${groupId}`).then((r) => r.data)
}
