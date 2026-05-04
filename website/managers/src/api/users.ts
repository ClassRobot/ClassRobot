import client from './client'
import type {
  PaginatedResponse,
  UserSummary,
  UserDetail,
  AdminPatchRequest,
} from '@/types/api'

export interface UserListParams {
  q?: string
  role?: string
  is_admin?: boolean
  page?: number
  page_size?: number
}

export function fetchUsers(params: UserListParams = {}): Promise<PaginatedResponse<UserSummary>> {
  return client.get('/users', { params }).then((r) => r.data)
}

export function fetchUserDetail(userId: number): Promise<UserDetail> {
  return client.get(`/users/${userId}`).then((r) => r.data)
}

export function patchUserAdmin(
  userId: number,
  payload: AdminPatchRequest,
): Promise<UserSummary> {
  return client.patch(`/users/${userId}/admin`, payload).then((r) => r.data)
}

export function deleteUserBind(
  userId: number,
  bindId: number,
): Promise<{ deleted: boolean; bind_id: number }> {
  return client.delete(`/users/${userId}/binds/${bindId}`).then((r) => r.data)
}
