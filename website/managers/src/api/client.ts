import axios from "axios";

import { clearStoredAdminToken, getStoredAdminToken } from "@/utils/admin-token";


export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? "/api/v1",
  timeout: 15000,
});


apiClient.interceptors.request.use((config) => {
  const token = getStoredAdminToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});


apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (axios.isAxiosError(error)) {
      const requestUrl = String(error.config?.url ?? "");
      const statusCode = error.response?.status;
      const isLoginFlow = requestUrl.includes("/admin/auth/login") || requestUrl.includes("/admin/auth/status");
      if (!isLoginFlow && (statusCode === 401 || statusCode === 403)) {
        clearStoredAdminToken();
        if (typeof window !== "undefined") {
          window.dispatchEvent(new Event("classrobot-admin-unauthorized"));
          if (!window.location.hash.startsWith("#/login")) {
            window.location.hash = "#/login";
          }
        }
      }
    }
    return Promise.reject(error);
  },
);


export function normalizeApiError(error: unknown): string {
  if (axios.isAxiosError(error)) {
    return (error.response?.data as { detail?: string } | undefined)?.detail ?? error.message;
  }
  return error instanceof Error ? error.message : "未知错误";
}
