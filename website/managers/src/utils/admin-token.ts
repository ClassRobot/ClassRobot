const ADMIN_TOKEN_KEY = "classrobot-admin-token";


export function getStoredAdminToken(): string {
  if (typeof window === "undefined") {
    return import.meta.env.VITE_ADMIN_API_TOKEN ?? "";
  }
  return localStorage.getItem(ADMIN_TOKEN_KEY) ?? import.meta.env.VITE_ADMIN_API_TOKEN ?? "";
}


export function setStoredAdminToken(token: string): void {
  localStorage.setItem(ADMIN_TOKEN_KEY, token.trim());
}


export function clearStoredAdminToken(): void {
  localStorage.removeItem(ADMIN_TOKEN_KEY);
}
