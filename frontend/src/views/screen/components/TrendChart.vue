<script setup lang="ts">
import { usePreferredReducedMotion } from "@vueuse/core";
import { computed } from "vue";

import { screenMotion, screenPalette } from "@/styles/motion-tokens";

import { useEchart, type ScreenEchartOption } from "../composables/useEchart";

const props = defineProps<{
  rows: Array<{ hour: string; total: number }>;
}>();

const motion = usePreferredReducedMotion();

const option = computed<ScreenEchartOption>(() => {
  const rows = props.rows ?? [];
  const labels = rows.map((row) => row.hour.slice(11, 16) || row.hour);
  const values = rows.map((row) => row.total);
  const reduce = motion.value === "reduce";

  return {
    backgroundColor: "transparent",
    animation: !reduce,
    animationDuration: screenMotion.chartDuration,
    animationEasing: "cubicOut",
    grid: { left: 52, right: 28, top: 24, bottom: 38 },
    tooltip: {
      trigger: "axis",
      backgroundColor: "rgba(0, 20, 43, 0.95)",
      borderColor: screenPalette.cyan,
      textStyle: { color: screenPalette.text },
      axisPointer: { lineStyle: { color: screenPalette.gold } },
    },
    xAxis: {
      type: "category",
      boundaryGap: false,
      data: labels,
      axisLine: { lineStyle: { color: "rgba(39, 216, 255, 0.28)" } },
      axisTick: { show: false },
      axisLabel: { color: screenPalette.textMuted, fontSize: 12, margin: 14 },
    },
    yAxis: {
      type: "value",
      minInterval: 1,
      splitLine: { lineStyle: { color: "rgba(39, 216, 255, 0.12)", type: "dashed" } },
      axisLabel: { color: screenPalette.textMuted, fontSize: 12 },
    },
    graphic: rows.length
      ? []
      : [{
          type: "text",
          left: "center",
          top: "middle",
          style: { text: "暂无趋势数据", fill: screenPalette.textMuted, fontSize: 16 },
        }],
    series: [
      {
        name: "通行量",
        type: "line",
        smooth: true,
        showSymbol: values.length <= 12,
        symbol: "circle",
        symbolSize: 7,
        lineStyle: {
          width: 4,
          color: screenPalette.cyan,
          shadowColor: "rgba(39, 216, 255, 0.55)",
          shadowBlur: 14,
        },
        itemStyle: { color: screenPalette.gold, borderColor: "#fff", borderWidth: 1 },
        areaStyle: {
          color: {
            type: "linear",
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: "rgba(39, 216, 255, 0.46)" },
              { offset: 0.55, color: "rgba(0, 61, 122, 0.18)" },
              { offset: 1, color: "rgba(0, 20, 43, 0)" },
            ],
          },
        },
        data: values,
      },
    ],
  };
});

const { chartRef } = useEchart(option);
</script>

<template>
  <div ref="chartRef" class="trend-chart" />
</template>

<style scoped>
.trend-chart {
  width: 100%;
  height: 100%;
  min-height: 0;
}
</style>
