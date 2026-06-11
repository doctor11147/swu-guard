/**
 * 多页签 store · 借鉴 vue-pure-admin lay-tag 的最小实现。
 * 切换路由时自动 push；点 × 关闭；右键菜单的"关闭其他/全部"行为留待后续。
 */
import { defineStore } from "pinia";
import type { RouteLocationNormalized } from "vue-router";

export interface TagItem {
  path: string;
  fullPath: string;
  title: string;
  name: string;
  /** 是否常驻（如首页，不可关闭） */
  pinned?: boolean;
}

const HOME: TagItem = {
  path: "/dashboard",
  fullPath: "/dashboard",
  title: "仪表盘",
  name: "Dashboard",
  pinned: true,
};

export const useTagsStore = defineStore("tags", {
  state: () => ({
    tags: [HOME] as TagItem[],
  }),
  actions: {
    open(route: RouteLocationNormalized) {
      // 不缓存：登录/大屏/404、被标记 hidden 的（除非已经在 tags 里）
      if (!route.name || !route.meta?.title) return;
      if (route.name === "Login" || route.name === "Screen" || route.name === "NotFound") return;

      const exists = this.tags.find((t) => t.path === route.path);
      if (!exists) {
        this.tags.push({
          path: route.path,
          fullPath: route.fullPath,
          title: route.meta.title as string,
          name: route.name as string,
        });
      } else {
        exists.fullPath = route.fullPath;
      }
    },
    close(path: string): string | null {
      const idx = this.tags.findIndex((t) => t.path === path);
      if (idx < 0) return null;
      const tag = this.tags[idx];
      if (tag.pinned) return null;
      this.tags.splice(idx, 1);
      // 返回应跳转的下个 tag
      const next = this.tags[idx] ?? this.tags[idx - 1] ?? HOME;
      return next.path;
    },
    closeOthers(path: string) {
      this.tags = this.tags.filter((t) => t.pinned || t.path === path);
    },
    closeAll(): string {
      this.tags = [HOME];
      return HOME.path;
    },
  },
});
