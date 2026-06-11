import { request } from "./http";
import type { AdminOut, TokenOut } from "./types";

export const authApi = {
  login(username: string, password: string) {
    return request<TokenOut>({
      url: "/auth/login",
      method: "POST",
      data: { username, password },
    });
  },
  me() {
    return request<AdminOut>({ url: "/auth/me", method: "GET" });
  },
  logout() {
    return request<{ ok: boolean }>({ url: "/auth/logout", method: "POST" });
  },
  changePassword(old_password: string, new_password: string) {
    return request<{ ok: boolean }>({
      url: "/auth/me/password",
      method: "PUT",
      data: { old_password, new_password },
    });
  },
};
