import axios from 'axios'
import type { AxiosInstance, InternalAxiosRequestConfig } from 'axios'
import { useAuthStore } from '@/composables/useAuth'

const baseURL = '/api/v1/manager'

const client: AxiosInstance = axios.create({
  baseURL,
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
})

// Inject the session token into every request.
client.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = useAuthStore().sessionToken
  if (token && config.headers) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Redirect to login on 401 responses.
client.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      useAuthStore().clearSession()
      // Only redirect if we're not already on the login page
      if (window.location.pathname !== '/manager/login') {
        window.location.href = '/manager/login'
      }
    }
    return Promise.reject(error)
  },
)

export default client
