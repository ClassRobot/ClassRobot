import client from './client'
import type { LoginRequest, TokenResponse, AuthMeResponse } from '@/types/api'

export function login(payload: LoginRequest): Promise<TokenResponse> {
  return client.post('/auth/login', payload).then((r) => r.data)
}

export function authMe(): Promise<AuthMeResponse> {
  return client.get('/auth/me').then((r) => r.data)
}

export function logout(): Promise<{ logged_out: boolean }> {
  return client.post('/auth/logout').then((r) => r.data)
}
