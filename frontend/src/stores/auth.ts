/**
 * 认证 store · 持久化（localStorage）。
 * 保存：access_token、refresh_token、当前用户。
 */
import { defineStore } from "pinia";

import { authApi } from "@/api/auth";
import { clearToken, setToken } from "@/api/http";
import type { AdminOut } from "@/api/types";

export const useAuthStore = defineStore("auth", {
  state: () => ({
    token: localStorage.getItem("swu_face_token") as string | null,
    user: null as AdminOut | null,
  }),
  getters: {
    isLoggedIn: (s) => !!s.token,
    role: (s) => s.user?.role ?? "viewer",
    isGuard: (s) => s.user?.role === "guard",
    isAdminLike: (s) =>
      s.user?.role === "superadmin" || s.user?.role === "admin",
    gateIds: (s) => s.user?.gate_ids ?? [],
  },
  actions: {
    async login(username: string, password: string) {
      const r = await authApi.login(username, password);
      setToken(r.access_token, r.refresh_token);
      this.token = r.access_token;
      this.user = r.user;
      return r;
    },
    async fetchMe() {
      try {
        this.user = await authApi.me();
      } catch {
        this.user = null;
      }
    },
    async logout() {
      try {
        await authApi.logout();
      } catch {
        /* ignore */
      }
      clearToken();
      this.token = null;
      this.user = null;
    },
  },
});
