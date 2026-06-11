<script setup lang="ts">
import { usePreferredReducedMotion } from "@vueuse/core";
import { computed } from "vue";

import type { AccessDecision } from "@/api/types";
import { screenMotion, screenPalette, swuMotionColors } from "@/styles/motion-tokens";

import { useEchart, type ScreenEchartOption } from "../composables/useEchart";

const props = defineProps<{
  rows: Array<{ name: string; value: number }>;
}>();

const motion = usePreferredReducedMotion();

const labelMap: Record<AccessDecision, string> = {
  granted: "通行",
  rejected: "未识别",
  spoof: "活体拒",
  no_face: "无脸",
};

const colorMap: Record<AccessDecision, string> = {
  granted: swuMotionColors.granted,
  rejected: swuMotionColors.rejected,
  spoof: swuMotionColors.spoof,
  no_face: swuMotionColors.network,
};

const option = computed<ScreenEchartOption>(() => {
  const reduce = motion.value === "reduce";
  const data = (props.rows ?? []).map((row) => {
    const key = row.name as AccessDecision;
    return {
      name: labelMap[key] ?? row.name,
      value: row.value,
      itemStyle: { color: colorMap[key] ?? screenPalette.cyan },
    };
  });

  return {
    backgroundColor: "transparent",
    animation: !reduce,
    animationDuration: screenMotion.chartDuration,
    animationEasing: "cubicOut",
    tooltip: {
      trigger: "item",
      backgroundColor: "rgba(0, 20, 43, 0.95)",
      borderColor: screenPalette.cyan,
      textStyle: { color: screenPalette.text },
    },
    legend: {
      bottom: 6,
      icon: "circle",
      itemWidth: 10,
      itemHeight: 10,
      textStyle: { color: screenPalette.textMuted, fontSize: 13 },
    },
    graphic: data.length
      ? [{
          type: "text",
          left: "center",
          top: "43%",
          style: {
            text: "DECISION",
            fill: screenPalette.textMuted,
            font: "700 14px DIN Alternate, monospace",
            align: "center",
          },
        }]
      : [{
          type: "text",
          left: "center",
          top: "middle",
          style: { text: "暂无分布数据", fill: screenPalette.textMuted, fontSize: 16 },
        }],
    series: [
      {
        name: "决策分布",
        type: "pie",
        radius: ["46%", "72%"],
        center: ["50%", "45%"],
        roseType: "radius",
        minAngle: 8,
        avoidLabelOverlap: true,
        label: { color: screenPalette.text, formatter: "{b}\n{d}%", fontSize: 12 },
        labelLine: { lineStyle: { color: "rgba(39, 216, 255, 0.36)" } },
        itemStyle: {
          borderColor: "rgba(0, 20, 43, 0.92)",
          borderWidth: 3,
          shadowBlur: 18,
          shadowColor: "rgba(39, 216, 255, 0.18)",
        },
        emphasis: { scale: !reduce, scaleSize: 10 },
        data,
      },
    ],
  };
});

const { chartRef } = useEchart(option);
</script>

<template>
  <div ref="chartRef" class="decision-pie" />
</template>

<style scoped>
.decision-pie {
  width: 100%;
  height: 100%;
  min-height: 0;
}
</style>
