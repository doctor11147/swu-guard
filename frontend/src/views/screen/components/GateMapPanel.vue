<script setup lang="ts">
import { usePreferredReducedMotion } from "@vueuse/core";
import { computed } from "vue";

import type { GateOut } from "@/api/types";
import { screenMotion, screenPalette, swuMotionColors } from "@/styles/motion-tokens";

import { useEchart, type ScreenEchartOption } from "../composables/useEchart";

const props = defineProps<{
  gates: GateOut[];
}>();

const motion = usePreferredReducedMotion();

const fallbackPositions = [
  { x: 18, y: 68 },
  { x: 31, y: 32 },
  { x: 48, y: 74 },
  { x: 58, y: 42 },
  { x: 70, y: 66 },
  { x: 82, y: 35 },
  { x: 88, y: 78 },
];

const statusMeta = {
  online: { label: "在线", color: swuMotionColors.granted },
  offline: { label: "离线", color: "#64748B" },
  disabled: { label: "停用", color: swuMotionColors.danger },
} as const;

const gatePoints = computed(() => (props.gates ?? []).map((gate, index) => {
  const point = fallbackPositions[index % fallbackPositions.length];
  return {
    ...gate,
    x: point.x + Math.floor(index / fallbackPositions.length) * 3,
    y: point.y - Math.floor(index / fallbackPositions.length) * 4,
  };
}));

const stats = computed(() => gatePoints.value.reduce(
  (acc, gate) => {
    acc[gate.status] += 1;
    return acc;
  },
  { online: 0, offline: 0, disabled: 0 } as Record<GateOut["status"], number>,
));

function buildSeries(status: GateOut["status"], reduce: boolean) {
  const color = statusMeta[status].color;
  const data = gatePoints.value
    .filter((gate) => gate.status === status)
    .map((gate) => ({
      name: gate.name,
      value: [gate.x, gate.y, 1],
      gate,
      itemStyle: { color },
      label: { color },
    }));

  return {
    name: statusMeta[status].label,
    type: status === "online" ? "effectScatter" : "scatter",
    coordinateSystem: "cartesian2d",
    data,
    symbolSize: status === "online" ? 17 : 14,
    rippleEffect: status === "online" && !reduce ? { scale: 5.4, brushType: "stroke", number: 3 } : undefined,
    showEffectOn: "render",
    label: {
      show: true,
      position: "bottom",
      distance: 8,
      formatter: "{b}",
      fontSize: 12,
      color: screenPalette.textMuted,
      textShadowColor: "rgba(0,0,0,0.75)",
      textShadowBlur: 4,
    },
    itemStyle: {
      color,
      borderColor: "#EAF4FF",
      borderWidth: status === "online" ? 2 : 1,
      shadowBlur: status === "online" ? 18 : 8,
      shadowColor: color,
    },
    emphasis: { scale: !reduce, focus: "series" },
  };
}

const option = computed<ScreenEchartOption>(() => {
  const reduce = motion.value === "reduce";
  return {
    backgroundColor: "transparent",
    animation: !reduce,
    animationDuration: screenMotion.chartDuration,
    animationEasing: "cubicOut",
    grid: { left: 6, right: 6, top: 6, bottom: 6, containLabel: false },
    tooltip: {
      trigger: "item",
      backgroundColor: "rgba(0, 20, 43, 0.96)",
      borderColor: screenPalette.cyan,
      textStyle: { color: screenPalette.text },
      formatter(params: { data?: { gate?: GateOut } }) {
        const gate = params.data?.gate;
        if (!gate) return "门禁节点";
        return `${gate.name}<br/>状态：${statusMeta[gate.status].label}<br/>方向：${gate.direction}<br/>位置：${gate.location || "--"}`;
      },
    },
    xAxis: { min: 0, max: 100, show: false },
    yAxis: { min: 0, max: 100, show: false },
    graphic: [
      {
        type: "group",
        left: "center",
        top: "middle",
        z: -10,
        children: [
          {
            type: "rect",
            shape: { x: -235, y: -128, width: 470, height: 256, r: 34 },
            style: { fill: "rgba(0, 61, 122, 0.12)", stroke: "rgba(39, 216, 255, 0.28)", lineWidth: 2 },
          },
          {
            type: "polyline",
            shape: { points: [[-196, 70], [-88, -42], [20, 38], [142, -72], [210, 34]] },
            style: { stroke: "rgba(212, 175, 55, 0.38)", lineWidth: 3, fill: "transparent" },
          },
          {
            type: "text",
            style: { text: "BEIBEI CAMPUS", x: -86, y: -8, fill: "rgba(234, 244, 255, 0.16)", font: "800 30px DIN Alternate" },
          },
        ],
      },
      gatePoints.value.length
        ? undefined
        : {
            type: "text",
            left: "center",
            top: "middle",
            style: { text: "暂无门禁节点", fill: screenPalette.textMuted, fontSize: 16 },
          },
    ].filter(Boolean),
    series: [buildSeries("online", reduce), buildSeries("offline", reduce), buildSeries("disabled", reduce)],
  };
});

const { chartRef } = useEchart(option);
</script>

<template>
  <div class="gate-map">
    <div ref="chartRef" class="gate-map__chart" />
    <div class="gate-map__legend">
      <span><i class="is-online" />在线 {{ stats.online }}</span>
      <span><i class="is-offline" />离线 {{ stats.offline }}</span>
      <span><i class="is-disabled" />停用 {{ stats.disabled }}</span>
    </div>
  </div>
</template>

<style scoped>
.gate-map {
  position: relative;
  width: 100%;
  height: 100%;
  min-height: 0;
  overflow: hidden;
  border-radius: 18px;
  background:
    linear-gradient(rgba(39, 216, 255, 0.06) 1px, transparent 1px),
    linear-gradient(90deg, rgba(39, 216, 255, 0.06) 1px, transparent 1px),
    radial-gradient(circle at 50% 48%, rgba(39, 216, 255, 0.12), transparent 54%);
  background-size: 34px 34px, 34px 34px, 100% 100%;
}

.gate-map::before {
  content: "";
  position: absolute;
  inset: 22px;
  border: 1px solid rgba(39, 216, 255, 0.16);
  border-radius: 28px;
  pointer-events: none;
}

.gate-map__chart {
  position: absolute;
  inset: 0;
}

.gate-map__legend {
  position: absolute;
  right: 18px;
  bottom: 14px;
  display: flex;
  gap: 14px;
  color: #b9d6ee;
  font-size: 13px;
  letter-spacing: 0.08em;
}

.gate-map__legend span {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.gate-map__legend i {
  width: 9px;
  height: 9px;
  border-radius: 999px;
  box-shadow: 0 0 12px currentColor;
}

.is-online { background: #20c36b; color: #20c36b; }
.is-offline { background: #64748b; color: #64748b; }
.is-disabled { background: #b22222; color: #b22222; }
</style>
