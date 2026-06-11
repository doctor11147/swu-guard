<!-- 视觉参考: skills/art-design-pro shadow-mode 卡片 + soybean-admin 列表 hover 层级。 -->
<script setup lang="ts">
import { ArrowRight, Location } from "@element-plus/icons-vue";
import type { GateOut } from "@/api/types";
import {
  bindGateMarkers,
  gateStatusClass,
  gateStatusLabel,
  type BoundGateMarker,
} from "./gateMarkers";
import { gateFocusKey, useGateFocus } from "./useGateFocus";

const props = defineProps<{
  gates: GateOut[];
}>();

const router = useRouter();
const gateFocus = inject(gateFocusKey, undefined) ?? useGateFocus();
const { activeGateNo, focusGate, scheduleHide, clearHide } = gateFocus;

const rows = computed(() =>
  bindGateMarkers(props.gates).sort((a, b) => a.gateNo - b.gateNo),
);

function gateTitle(row: BoundGateMarker) {
  return row.gate?.name || `第 ${row.gateNo} 校门`;
}

function gateLocation(row: BoundGateMarker) {
  return row.gate?.location || "位置未登记";
}

function enterGate(row: BoundGateMarker) {
  if (!row.gate) return;
  router.push(`/gates/${row.gate.id}/recognize`);
}

function onKeydown(event: KeyboardEvent, row: BoundGateMarker) {
  if (event.key !== "Enter" && event.key !== " ") return;
  event.preventDefault();
  enterGate(row);
}

function rowLabel(row: BoundGateMarker) {
  return `${gateTitle(row)}，状态${gateStatusLabel(row.gate?.status)}`;
}
</script>

<template>
  <div class="gate-list" role="list" aria-label="门禁入口列表">
    <article
      v-for="row in rows"
      :key="row.gateNo"
      :class="['gate-row', activeGateNo === row.gateNo && 'is-active', !row.gate && 'is-unbound']"
      role="button"
      tabindex="0"
      :aria-label="rowLabel(row)"
      @mouseenter="focusGate(row.gateNo)"
      @mouseleave="scheduleHide"
      @focus="focusGate(row.gateNo)"
      @blur="scheduleHide"
      @click="enterGate(row)"
      @keydown="onKeydown($event, row)"
    >
      <span class="accent" aria-hidden="true" />
      <div class="gate-no">{{ row.gateNo }}</div>

      <div class="gate-main">
        <div class="gate-title-row">
          <h3>{{ gateTitle(row) }}</h3>
          <span :class="['status-pill', gateStatusClass(row.gate?.status)]">
            <i aria-hidden="true" />
            {{ gateStatusLabel(row.gate?.status) }}
          </span>
        </div>
        <p class="gate-location">
          <el-icon><Location /></el-icon>
          <span>{{ gateLocation(row) }}</span>
        </p>
      </div>

      <button
        type="button"
        class="enter-btn"
        :disabled="!row.gate"
        @mouseenter="clearHide"
        @click.stop="enterGate(row)"
      >
        <span>进入</span>
        <el-icon><ArrowRight /></el-icon>
      </button>
    </article>
  </div>
</template>

<style scoped>
.gate-list {
  display: grid;
  gap: 13px;
  max-height: 690px;
  overflow-y: auto;
  padding: 2px 4px 2px 2px;
  scrollbar-width: thin;
}

.gate-list::-webkit-scrollbar {
  width: 6px;
}

.gate-list::-webkit-scrollbar-thumb {
  border-radius: 999px;
  background: rgba(27, 79, 142, 0.16);
}

.gate-row {
  position: relative;
  display: grid;
  grid-template-columns: 38px minmax(0, 1fr) auto;
  gap: 12px;
  align-items: center;
  min-height: 78px;
  padding: 14px 14px 14px 16px;
  border: 1px solid rgba(27, 79, 142, 0.08);
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.92);
  box-shadow: 0 6px 18px rgba(27, 79, 142, 0.06);
  cursor: pointer;
  outline: none;
  overflow: hidden;
  transition:
    transform 0.18s cubic-bezier(0.4, 0, 0.2, 1),
    box-shadow 0.18s cubic-bezier(0.4, 0, 0.2, 1),
    border-color 0.18s cubic-bezier(0.4, 0, 0.2, 1),
    background-color 0.18s cubic-bezier(0.4, 0, 0.2, 1);
}

.gate-row:hover,
.gate-row:focus-visible {
  transform: translateY(-2px);
  border-color: rgba(27, 79, 142, 0.18);
  background: rgba(0, 61, 122, 0.04);
  box-shadow: 0 12px 28px rgba(27, 79, 142, 0.12);
}

.gate-row.is-active {
  transform: translateY(-2px);
  border-color: rgba(0, 61, 122, 0.24);
  background: rgba(0, 61, 122, 0.07);
  box-shadow: 0 16px 34px rgba(27, 79, 142, 0.14);
}

.gate-row.is-unbound {
  cursor: default;
  opacity: 0.68;
}

.accent {
  position: absolute;
  left: 0;
  top: 12px;
  bottom: 12px;
  width: 3px;
  border-radius: 0 999px 999px 0;
  background: rgba(0, 61, 122, 0.22);
  transition: width 0.18s ease, background-color 0.18s ease;
}

.gate-row:hover .accent,
.gate-row:focus-visible .accent {
  width: 4px;
  background: rgba(0, 61, 122, 0.68);
}

.gate-row.is-active .accent {
  width: 5px;
  background: var(--xw-primary, #003d7a);
}

.gate-no {
  width: 38px;
  height: 38px;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  background: linear-gradient(135deg, var(--xw-primary, #003d7a), #2b6cb0);
  box-shadow: 0 8px 18px rgba(27, 79, 142, 0.22);
  font-size: 17px;
  font-weight: 800;
  font-variant-numeric: tabular-nums;
  transition: transform 0.18s ease, box-shadow 0.18s ease;
}

.gate-row.is-active .gate-no {
  transform: scale(1.06);
  box-shadow: 0 10px 22px rgba(27, 79, 142, 0.3);
}

.gate-main {
  min-width: 0;
}

.gate-title-row {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.gate-title-row h3 {
  margin: 0;
  color: var(--xw-text, #172033);
  font-size: 15px;
  line-height: 1.25;
  letter-spacing: 0;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.gate-location {
  display: flex;
  align-items: center;
  gap: 5px;
  margin: 7px 0 0;
  color: var(--xw-muted, #637083);
  font-size: 12px;
  line-height: 1.35;
}

.gate-location span {
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.status-pill {
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  gap: 5px;
  min-height: 22px;
  padding: 0 8px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
  white-space: nowrap;
}

.status-pill i {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
}

.status-pill.is-active {
  color: #0f7a42;
  background: #dff7eb;
}

.status-pill.is-maintenance {
  color: #9a5b00;
  background: #fff2cc;
}

.status-pill.is-disabled {
  color: #667085;
  background: #eef2f6;
}

.enter-btn {
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 5px;
  min-width: 72px;
  min-height: 36px;
  padding: 0 11px;
  border: 0;
  border-radius: 11px;
  color: #fff;
  background: linear-gradient(135deg, var(--xw-primary, #003d7a), #2b6cb0);
  font-weight: 700;
  cursor: pointer;
  box-shadow: 0 8px 18px rgba(27, 79, 142, 0.2);
  transition: transform 0.18s ease, box-shadow 0.18s ease;
}

.enter-btn:hover {
  transform: translateY(-1px);
  box-shadow: 0 12px 24px rgba(27, 79, 142, 0.28);
}

.enter-btn:disabled {
  color: #98a2b3;
  background: #edf1f5;
  box-shadow: none;
  cursor: not-allowed;
}

@media (max-width: 767px) {
  .gate-list {
    max-height: none;
    gap: 12px;
    padding-right: 0;
  }

  .gate-row {
    grid-template-columns: 42px minmax(0, 1fr) auto;
    min-height: 64px;
    padding: 13px 12px 13px 15px;
  }

  .gate-no {
    width: 42px;
    height: 42px;
  }

  .enter-btn {
    min-width: 64px;
  }
}

@media (max-width: 460px) {
  .gate-row {
    grid-template-columns: 42px minmax(0, 1fr);
  }

  .enter-btn {
    grid-column: 2;
    width: fit-content;
  }
}
</style>
