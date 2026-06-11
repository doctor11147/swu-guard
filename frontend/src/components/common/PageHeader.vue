<script setup lang="ts">
defineProps<{
  title: string;
  subtitle?: string;
}>();
</script>

<template>
  <div class="page-head">
    <div class="text">
      <h1 class="title">{{ title }}</h1>
      <p v-if="subtitle" class="sub">{{ subtitle }}</p>
    </div>
    <div class="actions">
      <slot name="actions" />
    </div>
  </div>
</template>

<style scoped>
.page-head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  margin-bottom: 18px;
  gap: 16px;
}
.title {
  margin: 0;
  font-size: 20px;
  font-weight: 700;
  color: var(--swu-text);
  letter-spacing: -0.02em;
  font-family: "Inter", "PingFang SC", "Hiragino Sans GB", -apple-system, BlinkMacSystemFont, sans-serif;
}
.sub {
  margin: 4px 0 0;
  font-size: 13px;
  color: var(--swu-text-3);
}
.actions {
  display: flex; gap: 10px; flex-shrink: 0;
}
</style>
