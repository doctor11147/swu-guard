<script setup lang="ts">
import { ScrollBoard } from "@kjgl77/datav-vue3";
import "@kjgl77/datav-vue3/dist/style.css";
import { computed } from "vue";

const props = defineProps<{
  rows: Array<{ faculty: string; total: number }>;
}>();

const boardConfig = computed(() => ({
  header: ["排名", "学部 / 学院", "通行"],
  data: (props.rows ?? []).map((row, index) => [
    `<span class="rank-no">${String(index + 1).padStart(2, "0")}</span>`,
    `<span class="rank-name">${row.faculty || "未分组"}</span>`,
    `<span class="rank-value">${row.total}</span>`,
  ]),
  rowNum: 7,
  headerBGC: "rgba(0, 61, 122, 0.55)",
  oddRowBGC: "rgba(39, 216, 255, 0.06)",
  evenRowBGC: "rgba(0, 61, 122, 0.13)",
  waitTime: 2200,
  headerHeight: 36,
  columnWidth: [72, 260],
  align: ["center", "left", "right"],
  carousel: "single",
}));
</script>

<template>
  <div class="rank-board">
    <ScrollBoard v-if="rows.length" class="rank-board__scroll" :config="boardConfig" />
    <div v-else class="rank-board__empty">暂无排行数据</div>
    <div class="rank-board__note">DataV ScrollBoard · 自动滚动排行</div>
  </div>
</template>

<style scoped>
.rank-board {
  position: relative;
  width: 100%;
  height: 100%;
  min-height: 0;
}

.rank-board__scroll {
  width: 100%;
  height: calc(100% - 26px);
  min-height: 220px;
  overflow: hidden;
  color: #eaf4ff;
}

.rank-board__scroll :deep(.dv-scroll-board) {
  width: 100%;
  height: 100%;
}

.rank-board__scroll :deep(.header) {
  color: #d7efff;
  font-size: 13px;
  font-weight: 800;
  letter-spacing: 0.1em;
}

.rank-board__scroll :deep(.row-item) {
  color: #b9d6ee;
  font-size: 14px;
}

.rank-board__scroll :deep(.rank-no) {
  color: #d4af37;
  font-family: "DIN Alternate", monospace;
  font-weight: 800;
}

.rank-board__scroll :deep(.rank-name) {
  display: inline-block;
  max-width: 220px;
  overflow: hidden;
  text-overflow: ellipsis;
  vertical-align: top;
  white-space: nowrap;
}

.rank-board__scroll :deep(.rank-value) {
  color: #27d8ff;
  font-family: "DIN Alternate", monospace;
  font-size: 18px;
  font-weight: 800;
  text-shadow: 0 0 14px rgba(39, 216, 255, 0.38);
}

.rank-board__empty {
  display: grid;
  height: calc(100% - 26px);
  min-height: 220px;
  place-items: center;
  color: #8aa8c7;
  font-size: 16px;
  letter-spacing: 0.12em;
}

.rank-board__note {
  position: absolute;
  right: 0;
  bottom: 0;
  color: #8aa8c7;
  font-size: 12px;
  letter-spacing: 0.08em;
  opacity: 0.78;
}
</style>
