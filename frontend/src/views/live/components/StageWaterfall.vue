<script setup lang="ts">
import { computed } from "vue";

import { screenPalette, swuMotionColors } from "@/styles/motion-tokens";
import { useEchart, type ScreenEchartOption } from "@/views/screen/composables/useEchart";

interface ServerTiming {
  detect?: number;
  align?: number;
  liveness?: number;
  quality?: number;
  embed?: number;
  retrieve?: number;
  total?: number;
}

const props = defineProps<{
  timing: ServerTiming | null;
  streaming: boolean;
}>();

const stageMeta = [
  { key: "detect", label: "检测", desc: "SCRFD", color: screenPalette.cyan },
  { key: "align", label: "对齐", desc: "5 点仿射", color: "#60A5FA" },
  { key: "liveness", label: "活体", desc: "Silent-FAS", color: swuMotionColors.spoof },
  { key: "quality", label: "质量", desc: "Quality Gate", color: screenPalette.gold },
  { key: "embed", label: "嵌入", desc: "EdgeFace", color: swuMotionColors.granted },
  { key: "retrieve", label: "检索", desc: "FAISS", color: "#8AA8C7" },
] as const;

function asMs(value: unknown) {
  const n = Number(value);
  return Number.isFinite(n) && n >= 0 ? n : 0;
}

function fmtMs(value: number) {
  return `${value.toFixed(value >= 100 ? 0 : 1)}ms`;
}

const rows = computed(() => stageMeta.map((stage) => ({
  ...stage,
  ms: asMs(props.timing?.[stage.key]),
})));

const hasTiming = computed(() => props.timing !== null && rows.value.some((item) => item.ms > 0));
const stageSum = computed(() => rows.value.reduce((sum, item) => sum + item.ms, 0));
const totalMs = computed(() => asMs(props.timing?.total) || stageSum.value);
const overheadMs = computed(() => Math.max(0, totalMs.value - stageSum.value));
const maxStageMs = computed(() => Math.max(1, ...rows.value.map((item) => item.ms)));

const option = computed<ScreenEchartOption>(() => ({
  backgroundColor: "transparent",
  animationDuration: 320,
  animationEasing: "cubicOut",
  grid: { left: 12, right: 18, top: 34, bottom: 24, containLabel: true },
  legend: {
    top: 0,
    left: 0,
    icon: "roundRect",
    itemWidth: 12,
    itemHeight: 8,
    textStyle: { color: screenPalette.textMuted, fontSize: 11 },
  },
  tooltip: {
    trigger: "axis",
    axisPointer: { type: "shadow" },
    backgroundColor: "rgba(0, 20, 43, 0.96)",
    borderColor: screenPalette.cyan,
    textStyle: { color: screenPalette.text },
    formatter(params: Array<{ seriesName?: string; value?: number; marker?: string }>) {
      const lines = params
        .filter((item) => Number(item.value) > 0)
        .map((item) => `${item.marker ?? ""}${item.seriesName}: ${fmtMs(Number(item.value ?? 0))}`);
      if (overheadMs.value > 0.05) lines.push(`框架/调度: ${fmtMs(overheadMs.value)}`);
      lines.push(`总计: ${fmtMs(totalMs.value)}`);
      return lines.join("<br/>");
    },
  },
  xAxis: {
    type: "value",
    min: 0,
    max: Math.max(totalMs.value, stageSum.value, 1),
    axisLabel: { color: screenPalette.textMuted, fontSize: 10, formatter: "{value}ms" },
    axisLine: { show: false },
    axisTick: { show: false },
    splitLine: { lineStyle: { color: "rgba(39, 216, 255, 0.10)", type: "dashed" } },
  },
  yAxis: {
    type: "category",
    data: ["服务端"],
    axisLabel: { color: screenPalette.text, fontSize: 12, fontWeight: 700 },
    axisLine: { show: false },
    axisTick: { show: false },
  },
  graphic: hasTiming.value
    ? []
    : [{
        type: "text",
        left: "center",
        top: "middle",
        style: {
          text: props.streaming ? "等待后端 timing 字段…" : "启动识别后显示真实阶段耗时",
          fill: screenPalette.textMuted,
          fontSize: 13,
        },
      }],
  series: rows.value.map((stage) => ({
    name: stage.label,
    type: "bar",
    stack: "server",
    barWidth: 28,
    data: [stage.ms],
    itemStyle: {
      color: stage.color,
      borderRadius: stage.key === "detect"
        ? [8, 0, 0, 8]
        : stage.key === "retrieve"
          ? [0, 8, 8, 0]
          : 0,
    },
    label: {
      show: stage.ms >= Math.max(8, totalMs.value * 0.08),
      position: "inside",
      color: "#00142B",
      fontWeight: 800,
      formatter: () => fmtMs(stage.ms),
    },
    emphasis: { focus: "series" },
  })),
}));

const { chartRef } = useEchart(option);
</script>

<template>
  <section class="stage-waterfall">
    <header class="stage-waterfall__header">
      <div>
        <div class="stage-waterfall__eyebrow">SERVER PIPELINE TIMING</div>
        <h3>服务端典型阶段耗时</h3>
      </div>
      <div class="stage-waterfall__total" :class="{ 'is-live': streaming && hasTiming }">
        <span>{{ hasTiming ? '最近一帧' : '待采样' }}</span>
        <strong>{{ fmtMs(totalMs) }}</strong>
      </div>
    </header>

    <div class="stage-waterfall__body">
      <div class="stage-waterfall__chart-wrap">
        <div ref="chartRef" class="stage-waterfall__chart" />
      </div>

      <div class="stage-waterfall__rows">
        <article v-for="stage in rows" :key="stage.key" class="stage-row">
          <div class="stage-row__top">
            <span><i :style="{ background: stage.color }" />{{ stage.label }} · {{ stage.desc }}</span>
            <strong>{{ fmtMs(stage.ms) }}</strong>
          </div>
          <div class="stage-row__bar">
            <b :style="{ width: `${Math.max(hasTiming ? 5 : 0, (stage.ms / maxStageMs) * 100)}%`, background: stage.color }" />
          </div>
        </article>
      </div>
    </div>

    <p class="stage-waterfall__note">
      本面板只读取 WS 返回的 timing 字段；与上方客户端往返延迟相减，可估算网络传输、JPEG/base64 编码与浏览器调度开销。
    </p>
  </section>
</template>

<style scoped>
.stage-waterfall {
  position: relative;
  overflow: hidden;
  margin-top: 14px;
  border: 1px solid rgba(39, 216, 255, 0.2);
  border-radius: 16px;
  background:
    radial-gradient(circle at 12% 0%, rgba(212, 175, 55, 0.14), transparent 32%),
    radial-gradient(circle at 100% 12%, rgba(39, 216, 255, 0.14), transparent 30%),
    linear-gradient(135deg, rgba(0, 20, 43, 0.82), rgba(0, 61, 122, 0.2));
  box-shadow: inset 0 0 28px rgba(39, 216, 255, 0.05), 0 18px 36px rgba(0, 0, 0, 0.14);
}

.stage-waterfall__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 16px 18px 12px;
  border-bottom: 1px solid rgba(39, 216, 255, 0.12);
}

.stage-waterfall__eyebrow {
  color: #d4af37;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.18em;
}

.stage-waterfall h3 {
  margin: 4px 0 0;
  color: #eaf4ff;
  font-size: 18px;
  letter-spacing: 0.1em;
}

.stage-waterfall__total {
  min-width: 116px;
  padding: 8px 12px;
  border: 1px solid rgba(39, 216, 255, 0.18);
  border-radius: 12px;
  background: rgba(0, 20, 43, 0.42);
  text-align: right;
}

.stage-waterfall__total span {
  display: block;
  color: #8aa8c7;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
}

.stage-waterfall__total strong {
  display: block;
  margin-top: 3px;
  color: #eaf4ff;
  font-family: Impact, "DIN Alternate", sans-serif;
  font-size: 28px;
  letter-spacing: 0.04em;
}

.stage-waterfall__total.is-live strong {
  color: #27d8ff;
  text-shadow: 0 0 16px rgba(39, 216, 255, 0.28);
}

.stage-waterfall__body {
  display: grid;
  grid-template-columns: minmax(320px, 1.2fr) minmax(280px, 1fr);
  gap: 14px;
  padding: 16px 18px 10px;
}

.stage-waterfall__chart-wrap,
.stage-waterfall__rows {
  min-height: 210px;
  border: 1px solid rgba(39, 216, 255, 0.12);
  border-radius: 12px;
  background: rgba(0, 20, 43, 0.35);
}

.stage-waterfall__chart {
  width: 100%;
  height: 100%;
  min-height: 210px;
}

.stage-waterfall__rows {
  display: flex;
  flex-direction: column;
  gap: 9px;
  padding: 12px;
}

.stage-row__top {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  color: #8aa8c7;
  font-size: 12px;
}

.stage-row__top span {
  display: inline-flex;
  align-items: center;
  gap: 7px;
}

.stage-row__top i {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  box-shadow: 0 0 10px currentColor;
}

.stage-row__top strong {
  color: #eaf4ff;
  font-family: "DIN Alternate", monospace;
}

.stage-row__bar {
  height: 6px;
  margin-top: 5px;
  overflow: hidden;
  border-radius: 999px;
  background: rgba(138, 168, 199, 0.16);
}

.stage-row__bar b {
  display: block;
  height: 100%;
  border-radius: inherit;
}

.stage-waterfall__note {
  margin: 0;
  padding: 0 18px 16px;
  color: #8aa8c7;
  font-size: 11px;
  line-height: 1.6;
}

@media (max-width: 1180px) {
  .stage-waterfall__body {
    grid-template-columns: 1fr;
  }
}
</style>
