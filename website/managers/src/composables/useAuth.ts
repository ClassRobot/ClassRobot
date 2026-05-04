/**
 * Simple reactive auth store.
 * In-memory only — session token is lost on page refresh,
 * which causes a redirect to login (matching the backend's stateless design).
 */
import { reactive } from 'vue'

interface AuthState {
  sessionToken: string | null
  expiresAt: string | null
}

const state = reactive<AuthState>({
  sessionToken: null,
  expiresAt: null,
})

export function useAuthStore() {
  return {
    get sessionToken() {
      return state.sessionToken
    },
    get isAuthenticated() {
      return state.sessionToken !== null
    },

    setSession(token: string, expiresAt: string) {
      state.sessionToken = token
      state.expiresAt = expiresAt
    },

    clearSession() {
      state.sessionToken = null
      state.expiresAt = null
    },
  }
}
