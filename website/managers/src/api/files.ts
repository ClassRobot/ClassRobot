import client from './client'
import type {
  FileSpaceDetail,
  FileSpaceDirectoryCreateRequest,
  FileSpaceDirectoryCreateResult,
  FileSpaceEntriesResponse,
  FileSpaceKind,
  FileSpaceListResponse,
  FileSpaceTextPreview,
  FileSpaceWriteRequest,
  FileSpaceWriteResult,
  FileSpaceDeleteResult,
} from '@/types/api'

export function fetchFileSpaces(params: { kind?: FileSpaceKind; q?: string } = {}): Promise<FileSpaceListResponse> {
  return client.get('/files/spaces', { params }).then((r) => r.data)
}

export function fetchFileSpaceDetail(kind: FileSpaceKind, ownerId: string): Promise<FileSpaceDetail> {
  return client.get(`/files/spaces/${kind}/${encodeURIComponent(ownerId)}`).then((r) => r.data)
}

export function fetchFileSpaceEntries(
  kind: FileSpaceKind,
  ownerId: string,
  params: { path?: string } = {},
): Promise<FileSpaceEntriesResponse> {
  return client.get(`/files/spaces/${kind}/${encodeURIComponent(ownerId)}/entries`, { params }).then((r) => r.data)
}

export function readFileSpaceText(
  kind: FileSpaceKind,
  ownerId: string,
  params: { path: string; limit?: number },
): Promise<FileSpaceTextPreview> {
  return client.get(`/files/spaces/${kind}/${encodeURIComponent(ownerId)}/read`, { params }).then((r) => r.data)
}

export function writeFileSpaceText(
  kind: FileSpaceKind,
  ownerId: string,
  payload: FileSpaceWriteRequest,
): Promise<FileSpaceWriteResult> {
  return client.put(`/files/spaces/${kind}/${encodeURIComponent(ownerId)}/write`, payload).then((r) => r.data)
}

export function createFileSpaceDirectory(
  kind: FileSpaceKind,
  ownerId: string,
  payload: FileSpaceDirectoryCreateRequest,
): Promise<FileSpaceDirectoryCreateResult> {
  return client.post(`/files/spaces/${kind}/${encodeURIComponent(ownerId)}/directories`, payload).then((r) => r.data)
}

export function deleteFileSpaceEntry(
  kind: FileSpaceKind,
  ownerId: string,
  params: { path: string; recursive?: boolean; force?: boolean },
): Promise<FileSpaceDeleteResult> {
  return client.delete(`/files/spaces/${kind}/${encodeURIComponent(ownerId)}/entry`, { params }).then((r) => r.data)
}
