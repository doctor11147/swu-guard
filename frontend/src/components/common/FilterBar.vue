<script setup lang="ts">
/** 筛选栏外壳，借鉴 vue-pure-admin/list 的卡片样式。 */
defineProps<{ inline?: boolean }>();
</script>

<template>
  <div class="filter-bar">
    <slot />
    <div class="actions">
      <slot name="actions" />
    </div>
  </div>
</template>

<style scoped>
.filter-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
  padding: 14px 18px;
  background: var(--swu-bg-elev);
  border: 1px solid var(--swu-border);
  border-radius: 12px;
  margin-bottom: 14px;
}
.filter-bar :deep(.el-input),
.filter-bar :deep(.el-select),
.filter-bar :deep(.el-date-picker),
.filter-bar :deep(.el-input-number) {
  width: 200px;
}
.actions {
  margin-left: auto;
  display: flex;
  gap: 8px;
}
</style>
