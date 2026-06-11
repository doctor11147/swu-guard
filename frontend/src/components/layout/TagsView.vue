<script setup lang="ts">
/** 多页签 · 借鉴 vue-pure-admin lay-tag 但去掉拖动、右键菜单等复杂功能。 */
import { Close } from "@element-plus/icons-vue";

import { useTagsStore } from "@/stores/tags";

const tagsStore = useTagsStore();
const route = useRoute();
const router = useRouter();

// 路由切换时自动添加 tag
watchEffect(() => tagsStore.open(route));

function go(path: string) {
  if (path !== route.path) router.push(path);
}

function close(path: string, event: Event) {
  event.stopPropagation();
  const next = tagsStore.close(path);
  if (next && path === route.path) router.push(next);
}

const containerRef = ref<HTMLElement>();
// 当前激活 tag 滚动至可视区
watch(
  () => route.path,
  async () => {
    await nextTick();
    const el = containerRef.value?.querySelector<HTMLElement>(".tag.is-active");
    el?.scrollIntoView({ block: "nearest", inline: "center", behavior: "smooth" });
  },
  { immediate: true },
);
</script>

<template>
  <div ref="containerRef" class="tags-view">
    <div
      v-for="t in tagsStore.tags"
      :key="t.path"
      :class="['tag', t.path === route.path && 'is-active']"
      @click="go(t.fullPath)"
    >
      <span class="dot" v-if="t.path === route.path" />
      <span class="title">{{ t.title }}</span>
      <el-icon
        v-if="!t.pinned"
        class="close"
        @click="(e) => close(t.path, e)"
      >
        <Close />
      </el-icon>
    </div>
  </div>
</template>

<style scoped>
.tags-view {
  height: 40px;
  background: var(--swu-bg-elev);
  border-bottom: 1px solid var(--swu-border);
  display: flex; align-items: center; gap: 6px;
  padding: 0 12px;
  overflow-x: auto;
  scrollbar-width: none;
  flex-shrink: 0;
}
.tags-view::-webkit-scrollbar { display: none; }

.tag {
  position: relative;
  display: inline-flex; align-items: center; gap: 6px;
  padding: 5px 10px 5px 12px;
  font-size: 12px;
  color: var(--swu-text-2);
  background: transparent;
  border: 1px solid transparent;
  border-radius: 6px;
  cursor: pointer;
  user-select: none;
  white-space: nowrap;
  transition: all 0.15s ease;
}
.tag:hover {
  color: var(--swu-blue);
  background: var(--swu-blue-50);
}
.tag.is-active {
  color: #fff;
  background: linear-gradient(135deg, #003D7A, #1565C0);
  border-color: transparent;
  box-shadow: 0 2px 8px rgba(0, 61, 122, 0.18);
}
.tag.is-active:hover { color: #fff; }

.dot {
  width: 6px; height: 6px;
  border-radius: 50%;
  background: #D4AF37;
  box-shadow: 0 0 6px #D4AF37;
}

.title { line-height: 1; }

.close {
  margin-left: 2px;
  width: 14px; height: 14px;
  padding: 1px;
  border-radius: 4px;
  font-size: 11px;
  opacity: 0.6;
  transition: all 0.12s ease;
}
.close:hover { background: rgba(255,255,255,0.18); opacity: 1; }
.tag:not(.is-active) .close:hover { background: rgba(0,0,0,0.06); color: var(--swu-danger); }

:global(html.dark) .tag:hover {
  background: rgba(255, 255, 255, 0.04);
}
</style>
