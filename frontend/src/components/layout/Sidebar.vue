<script setup lang="ts">
/**
 * 玻璃拟态侧栏 · 借鉴 art-design-pro lay-sidebar + soybean-admin global-sider
 *
 * 视觉特征：
 * - 半透明背景 + backdrop-blur（玻璃拟态）
 * - 金色指示条 + 当前项微光
 * - 折叠平滑过渡，分组标签在折叠态消失
 */
import * as Icons from "@element-plus/icons-vue";

import { groupDefs, routes } from "@/router/routes";
import { useAppStore } from "@/stores/app";
import { useAuthStore } from "@/stores/auth";

interface MenuItem {
  name: string;
  path: string;
  title: string;
  icon: string;
  group: string;
  roles?: string[];
}

const app = useAppStore();
const auth = useAuthStore();
const router = useRouter();
const currentRoute = useRoute();

const allItems = computed<MenuItem[]>(() => {
  const list: MenuItem[] = [];
  const root = routes.find((r) => r.meta?.requiresAuth && Array.isArray(r.children));
  for (const c of root?.children ?? []) {
    if (c.meta?.hidden || !c.name || !c.meta?.group) continue;
    list.push({
      name: c.name as string,
      path: c.path,
      title: (c.meta.title as string) ?? "",
      icon: (c.meta.icon as string) ?? "Document",
      group: c.meta.group as string,
      roles: (c.meta.roles as string[]) || undefined,
    });
  }
  return list;
});

const visibleItems = computed(() =>
  allItems.value.filter((it) => {
    if (!it.roles) return true;
    return it.roles.includes(auth.role);
  }),
);

const grouped = computed(() => {
  const out: Array<{ key: string; label: string; items: MenuItem[] }> = [];
  for (const g of groupDefs) {
    const items = visibleItems.value.filter((it) => it.group === g.key);
    if (items.length) out.push({ key: g.key, label: g.label, items });
  }
  return out;
});

function go(path: string) { router.push(path); }

const collapsed = computed(() => app.sidebarCollapsed);

function getIcon(name: string) {
  return (Icons as Record<string, unknown>)[name] ?? Icons.Document;
}

function isActive(item: MenuItem): boolean {
  if (
    item.path === "/persons" &&
    currentRoute.path.startsWith("/persons/") &&
    currentRoute.path !== "/persons/capture"
  ) return true;
  return currentRoute.path === item.path;
}
</script>

<template>
  <aside :class="['sidebar', collapsed && 'is-collapsed']">
    <!-- 品牌标识 -->
    <div class="brand" @click="go('/dashboard')">
      <img src="/brand/swu-logo.png" class="brand-logo" alt="SWU" />
      <transition name="sidebar-fade">
        <div v-if="!collapsed" class="brand-text">
          <div class="brand-zh">西小卫</div>
          <div class="brand-en">
            <span v-if="auth.isGuard">门卫工作台 · {{ auth.gateIds.length }} 门</span>
            <span v-else>SWU-Guard</span>
          </div>
        </div>
      </transition>
    </div>

    <!-- 分组菜单 -->
    <nav class="menu">
      <template v-for="g in grouped" :key="g.key">
        <div v-if="!collapsed" class="group-label">{{ g.label }}</div>
        <div
          v-for="item in g.items"
          :key="item.name"
          :class="['item', isActive(item) && 'is-active']"
          :title="collapsed ? item.title : undefined"
          @click="go(item.path)"
        >
          <span class="bar" />
          <el-icon class="icon" :size="19">
            <component :is="getIcon(item.icon)" />
          </el-icon>
          <transition name="sidebar-fade">
            <span v-if="!collapsed" class="text">{{ item.title }}</span>
          </transition>
        </div>
      </template>
    </nav>

    <!-- 数据大屏入口 -->
    <div
      class="screen-entry"
      :title="collapsed ? '数据大屏' : undefined"
      @click="go('/screen')"
    >
      <el-icon :size="19"><DataLine /></el-icon>
      <transition name="sidebar-fade">
        <span v-if="!collapsed">数据大屏</span>
      </transition>
    </div>
  </aside>
</template>

<style scoped>
.sidebar {
  width: 234px;
  height: 100vh;
  /* 玻璃拟态：半透明西大蓝 + 模糊 */
  background: linear-gradient(
    180deg,
    rgba(0, 40, 85, 0.97) 0%,
    rgba(0, 61, 122, 0.94) 40%,
    rgba(0, 61, 122, 0.92) 100%
  );
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  color: rgba(255, 255, 255, 0.88);
  display: flex;
  flex-direction: column;
  transition: width 0.28s cubic-bezier(0.16, 1, 0.3, 1);
  position: relative;
  overflow: hidden;
  flex-shrink: 0;
  border-right: 1px solid rgba(255, 255, 255, 0.08);
}
/* 顶部金色细线 */
.sidebar::before {
  content: "";
  position: absolute; top: 0; left: 0; right: 0; height: 2px;
  background: linear-gradient(90deg, transparent, #D4AF37 30%, #D4AF37 70%, transparent);
  opacity: 0.8;
}
.sidebar.is-collapsed { width: 66px; }

/* ==================== Brand ==================== */
.brand {
  display: flex; align-items: center; gap: 12px;
  padding: 20px 16px 18px;
  cursor: pointer;
  user-select: none;
  flex-shrink: 0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  margin-bottom: 4px;
}
.brand-logo {
  width: 32px; height: 32px; object-fit: contain;
  filter: drop-shadow(0 2px 4px rgba(0, 0, 0, 0.4));
  flex-shrink: 0;
}
.brand-zh {
  font-size: 16px; font-weight: 700; letter-spacing: 0.05em; white-space: nowrap;
  color: #fff;
}
.brand-en {
  font-size: 10px; opacity: 0.48; letter-spacing: 0.16em;
  white-space: nowrap; margin-top: 2px;
  font-weight: 400;
}

/* ==================== Menu ==================== */
.menu {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 4px 10px 16px;
}
.menu::-webkit-scrollbar { width: 4px; }
.menu::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.10);
  border-radius: 2px;
}

.group + .group { margin-top: 10px; }
.group-label {
  padding: 10px 14px 6px;
  font-size: 10px;
  font-weight: 600;
  opacity: 0.35;
  letter-spacing: 0.18em;
  text-transform: uppercase;
}

.item {
  position: relative;
  display: flex; align-items: center; gap: 12px;
  padding: 10px 14px;
  margin: 1px 0;
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.18s cubic-bezier(0.16, 1, 0.3, 1);
  white-space: nowrap;
  color: rgba(255, 255, 255, 0.72);
  font-size: 14px;
}
/* 金色侧标 */
.item .bar {
  position: absolute; left: -10px; top: 50%; transform: translateY(-50%);
  width: 3px; height: 0;
  background: #D4AF37;
  border-radius: 0 4px 4px 0;
  transition: height 0.22s cubic-bezier(0.16, 1, 0.3, 1);
}
.item:hover {
  background: rgba(255, 255, 255, 0.08);
  color: #fff;
}
.item.is-active {
  background: rgba(255, 255, 255, 0.12);
  color: #fff;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15), inset 0 0 0 1px rgba(255, 255, 255, 0.06);
}
.item.is-active .bar { height: 20px; }
.item .icon {
  color: rgba(255, 255, 255, 0.66);
  flex-shrink: 0;
  transition: color 0.18s ease;
}
.item:hover .icon { color: rgba(255, 255, 255, 0.9); }
.item.is-active .icon { color: #D4AF37; }
.item .text { font-size: 13.5px; font-weight: 500; }

.is-collapsed .item { justify-content: center; padding: 11px 0; }
.is-collapsed .group-label { display: none; }

/* ==================== 大屏入口 ==================== */
.screen-entry {
  display: flex; align-items: center; gap: 12px;
  padding: 14px 16px;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
  font-size: 13px;
  cursor: pointer;
  transition: all 0.18s ease;
  background: linear-gradient(135deg, rgba(212, 175, 55, 0.05) 0%, transparent 50%);
  color: rgba(255, 255, 255, 0.66);
  flex-shrink: 0;
}
.screen-entry:hover {
  background: linear-gradient(135deg, rgba(212, 175, 55, 0.14) 0%, transparent 60%);
  color: #fff;
}
.screen-entry .el-icon { color: #D4AF37; }
.is-collapsed .screen-entry { justify-content: center; padding: 14px 0; }

/* ==================== 动画 ==================== */
.sidebar-fade-enter-active,
.sidebar-fade-leave-active { transition: opacity 0.18s ease; }
.sidebar-fade-enter-from,
.sidebar-fade-leave-to { opacity: 0; }
</style>
