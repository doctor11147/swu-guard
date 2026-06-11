/**
 * 应用级 UI 状态：侧栏折叠、暗黑模式。
 */
import { defineStore } from "pinia";

export const useAppStore = defineStore("app", {
  state: () => ({
    sidebarCollapsed: localStorage.getItem("swu_sidebar") === "1",
    dark: localStorage.getItem("swu_dark") === "1",
  }),
  actions: {
    toggleSidebar() {
      this.sidebarCollapsed = !this.sidebarCollapsed;
      localStorage.setItem("swu_sidebar", this.sidebarCollapsed ? "1" : "0");
    },
    toggleDark() {
      this.dark = !this.dark;
      localStorage.setItem("swu_dark", this.dark ? "1" : "0");
      document.documentElement.classList.toggle("dark", this.dark);
    },
    syncDark() {
      document.documentElement.classList.toggle("dark", this.dark);
    },
  },
});
