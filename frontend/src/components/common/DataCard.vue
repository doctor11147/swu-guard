<script setup lang="ts">
/**
 * 数据卡片容器 · 借鉴 art-design-pro art-card（阴影模式 + hover 上浮）
 */
defineProps<{
  pad?: string;
  flush?: boolean;
}>();
</script>

<template>
  <section :class="['data-card', flush && 'is-flush']" :style="pad ? `padding: ${pad}` : undefined">
    <div v-if="$slots.header" class="head">
      <slot name="header" />
    </div>
    <div class="body">
      <slot />
    </div>
  </section>
</template>

<style scoped>
.data-card {
  background: var(--swu-bg-elev);
  border: 1px solid var(--swu-border);
  border-radius: var(--swu-radius-lg);
  box-shadow: var(--swu-shadow-sm);
  padding: 18px 20px;
  transition: transform var(--swu-transition), box-shadow var(--swu-transition);
}
.data-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--swu-shadow);
}
.data-card + .data-card { margin-top: 14px; }
.data-card.is-flush + .data-card { margin-top: 0; }

.head {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 14px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--swu-divider);
}
.head:empty { display: none; }
</style>
