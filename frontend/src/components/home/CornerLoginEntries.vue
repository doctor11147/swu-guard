<!-- 参考来源: skills/vue-element-plus-admin/src/components/Icon -->
<script setup lang="ts">
import { Key, User, UserFilled } from "@element-plus/icons-vue";

import { zhCN } from "@/i18n/zh-CN";

const entries = [
  { label: zhCN.home.adminLogin, icon: UserFilled, to: "/login?role=admin" },
  { label: zhCN.home.guardLogin, icon: Key, to: "/login?role=guard" },
  { label: zhCN.home.visitorEntry, icon: User, to: "/visitor" },
];
</script>

<template>
  <nav class="corner-entries" aria-label="登录入口">
    <RouterLink
      v-for="entry in entries"
      :key="entry.label"
      :to="entry.to"
      class="entry"
      :aria-label="entry.label"
    >
      <el-icon>
        <component :is="entry.icon" />
      </el-icon>
      <span>{{ entry.label }}</span>
    </RouterLink>
  </nav>
</template>

<style scoped>
.corner-entries {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
  flex-wrap: wrap;
}

.entry {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-height: 34px;
  padding: 0 10px;
  border: 1px solid rgba(27, 79, 142, 0.14);
  border-radius: 999px;
  color: var(--xw-primary);
  background: rgba(255, 255, 255, 0.72);
  text-decoration: none;
  font-size: 13px;
  transition: background 200ms cubic-bezier(0.4, 0, 0.2, 1),
    border-color 200ms cubic-bezier(0.4, 0, 0.2, 1);
}

.entry:hover {
  background: #fff;
  border-color: rgba(27, 79, 142, 0.32);
}
</style>
