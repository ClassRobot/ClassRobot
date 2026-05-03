import { defineStore } from "pinia";

import { fetchAdminMe } from "@/api/modules/admin";
import type { AdminUserItem } from "@/types/admin";
import { clearStoredAdminToken, getStoredAdminToken, setStoredAdminToken } from "@/utils/admin-token";


export const useAuthStore = defineStore("admin-auth", {
  state: () => ({
    token: getStoredAdminToken(),
    user: null as AdminUserItem | null,
    bootstrapped: !Boolean(getStoredAdminToken()),
  }),
  getters: {
    isAuthenticated: (state) => Boolean(state.token),
    displayName: (state) => state.user?.nickname || state.user?.username || "管理员",
  },
  actions: {
    updateToken(token: string) {
      this.token = token.trim();
      setStoredAdminToken(this.token);
      this.bootstrapped = true;
    },
    setCurrentUser(user: AdminUserItem | null) {
      this.user = user;
      this.bootstrapped = true;
    },
    updateSession(token: string, user: AdminUserItem) {
      this.token = token.trim();
      this.user = user;
      this.bootstrapped = true;
      setStoredAdminToken(this.token);
    },
    async bootstrap() {
      if (!this.token) {
        this.user = null;
        this.bootstrapped = true;
        return null;
      }
      try {
        const user = await fetchAdminMe();
        this.user = user;
        this.bootstrapped = true;
        return user;
      } catch (error) {
        this.logout();
        throw error;
      }
    },
    logout() {
      this.token = "";
      this.user = null;
      this.bootstrapped = true;
      clearStoredAdminToken();
    },
  },
});
