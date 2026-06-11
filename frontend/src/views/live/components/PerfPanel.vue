<script setup lang="ts">
import { LineChart } from "echarts/charts";
import { GraphicComponent, GridComponent, TooltipComponent } from "echarts/components";
import { init, use } from "echarts/core";
import type { EChartsCoreOption, EChartsType } from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import gsap from "gsap";
import { computed, nextTick, onActivated, onBeforeUnmount, onDeactivated, onMounted, ref, watch } from "vue";
import { usePreferredReducedMotion } from "@vueuse/core";

import { motionDurations, motionEase, screenPalette } from "@/styles/motion-tokens";

import type { PerfMonitor } from "../composables/usePerfMonitor";

const props = defineProps<{
  monitor: PerfMonitor;
  streaming: boolean;
}>();

let echartsRegistered = false;
function registerEcharts() {
  if (echartsRegistered) return;
  use([CanvasRenderer, LineChart, GridComponent, TooltipComponent, GraphicComponent]);
  echartsRegistered = true;
}
registerEcharts();

const rootRef = ref<HTMLElement | null>(null);
const chartRef = ref<HTMLDivElement | null>(null);
const collapsed = ref(false);
const visible = ref(true);
const reducedMotion = usePreferredReducedMotion();

let chart: EChartsType | null = null;
let resizeTimer: number | null = null;
let entranceCtx: gsap.Context | null = null;
let resizeBound = false;

const stats = computed(() => props.monitor.stats.value);
const fps = computed(() => props.monitor.fps.value);
const samples = computed(() => props.monitor.samples.value);

function latencyTone(value: number | null) {
  if (value == null) return "idle";
  if (value > 800) return "danger";
  if (value > 400) return "warning";
  return "good";
}

function fpsTone(value: number) {
  if (!props.streaming && value <= 0) return "idle";
  if (value < 2) return "warning";
  return "good";
}

function fmtMs(value: number | null) {
  return value == null ? "—" : value.toFixed(1);
}

const metricCards = computed(() => [
  { key: "current", label: "当前延迟", value: fmtMs(stats.value.current), unit: "ms", tone: latencyTone(stats.value.current) },
  { key: "avg", label: "平均延迟", value: fmtMs(stats.value.avg), unit: "ms", tone: latencyTone(stats.value.avg) },
  { key: "p95", label: "P95 延迟", value: fmtMs(stats.value.p95), unit: "ms", tone: latencyTone(stats.value.p95) },
  { key: "fps", label: "响应 FPS", value: fps.value.toFixed(1), unit: "fps", tone: fpsTone(fps.value) },
]);

const chartOption = computed<EChartsCoreOption>(() => {
  const rows = samples.value;
  return {
    backgroundColor: "transparent",
    animation: reducedMotion.value !== "reduce",
    animationDuration: 260,
    animationEasing: "cubicOut",
    grid: { left: 42, right: 16, top: 18, bottom: 28 },
    tooltip: {
      trigger: "axis",
      backgroundColor: "rgba(0, 20, 43, 0.96)",
      borderColor: screenPalette.cyan,
      textStyle: { color: screenPalette.text },
      formatter(params: Array<{ data?: number; axisValue?: string }>) {
        const item = params[0];
        return `帧 ${item?.axisValue ?? "--"}<br/>延迟 ${Number(item?.data ?? 0).toFixed(1)} ms`;
      },
    },
    xAxis: {
      type: "category",
      data: rows.map((item) => String(item.seq)),
      boundaryGap: false,
      axisTick: { show: false },
      axisLine: { lineStyle: { color: "rgba(39, 216, 255, 0.24)" } },
      axisLabel: { color: screenPalette.textMuted, fontSize: 10, interval: Math.max(0, Math.floor(rows.length / 6)) },
    },
    yAxis: {
      type: "value",
      min: 0,
      minInterval: 100,
      axisLabel: { color: screenPalette.textMuted, fontSize: 10, formatter: "{value}" },
      splitLine: { lineStyle: { color: "rgba(39, 216, 255, 0.10)", type: "dashed" } },
    },
    graphic: rows.length
      ? []
      : [{
          type: "text",
          left: "center",
          top: "middle",
          style: { text: "启动识别后开始采样", fill: screenPalette.textMuted, fontSize: 13 },
        }],
    series: [
      {
        name: "端到端延迟",
        type: "line",
        data: rows.map((item) => item.latency),
        smooth: true,
        showSymbol: rows.length < 16,
        symbolSize: 5,
        lineStyle: {
          width: 3,
          color: screenPalette.cyan,
          shadowColor: "rgba(39, 216, 255, 0.45)",
          shadowBlur: 10,
        },
        itemStyle: { color: screenPalette.gold },
        areaStyle: {
          color: {
            type: "linear",
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: "rgba(39, 216, 255, 0.36)" },
              { offset: 1, color: "rgba(39, 216, 255, 0)" },
            ],
          },
        },
      },
    ],
  };
});

function setChartOption() {
  if (!chart) return;
  chart.setOption(chartOption.value, { notMerge: false, lazyUpdate: true });
}

function resizeChart() {
  if (resizeTimer !== null) clearTimeout(resizeTimer);
  resizeTimer = window.setTimeout(() => {
    chart?.resize();
    resizeTimer = null;
  }, 120);
}

function bindResize() {
  if (resizeBound) return;
  window.addEventListener("resize", resizeChart);
  resizeBound = true;
}

function unbindResize() {
  if (resizeTimer !== null) {
    clearTimeout(resizeTimer);
    resizeTimer = null;
  }
  if (!resizeBound) return;
  window.removeEventListener("resize", resizeChart);
  resizeBound = false;
}

async function mountChart() {
  await nextTick();
  if (!chartRef.value || chart) return;
  chart = init(chartRef.value, undefined, { renderer: "canvas" });
  setChartOption();
  bindResize();
}

function disposeChart() {
  unbindResize();
  chart?.dispose();
  chart = null;
}

async function runEntranceMotion() {
  entranceCtx?.revert();
  entranceCtx = null;
  await nextTick();
  if (reducedMotion.value === "reduce" || !rootRef.value) return;
  entranceCtx = gsap.context(() => {
    gsap.from(".perf-panel__metric", {
      opacity: 0,
      y: 10,
      duration: motionDurations.base,
      ease: motionEase.standard,
      stagger: 0.035,
    });
  }, rootRef.value);
}

function cleanupEntranceMotion() {
  entranceCtx?.revert();
  entranceCtx = null;
}

watch(chartOption, () => setChartOption(), { deep: true, flush: "post" });
watch(collapsed, async (next) => {
  if (!next) {
    await nextTick();
    resizeChart();
  }
});
watch(visible, async (next) => {
  if (next) {
    await mountChart();
    void runEntranceMotion();
  } else {
    cleanupEntranceMotion();
    disposeChart();
  }
});

onMounted(() => {
  void mountChart();
  void runEntranceMotion();
});
onActivated(() => {
  void mountChart();
  void runEntranceMotion();
});
onDeactivated(() => {
  cleanupEntranceMotion();
  disposeChart();
});
onBeforeUnmount(() => {
  cleanupEntranceMotion();
  disposeChart();
});
</script>

<template>
  <section v-if="visible" ref="rootRef" class="perf-panel">
    <header class="perf-panel__header">
      <div>
        <div class="perf-panel__eyebrow">PERFORMANCE OBSERVABILITY</div>
        <h3>性能观测</h3>
      </div>
      <div class="perf-panel__status" :class="streaming ? 'is-live' : 'is-idle'">
        <span />{{ streaming ? '旁路采样中' : '待启动' }}
      </div>
      <div class="perf-panel__actions">
        <button type="button" @click="collapsed = !collapsed">{{ collapsed ? '展开' : '折叠' }}</button>
        <button type="button" @click="visible = false">隐藏</button>
      </div>
    </header>

    <div v-show="!collapsed" class="perf-panel__body">
      <div class="perf-panel__metrics">
        <article
          v-for="item in metricCards"
          :key="item.key"
          :class="['perf-panel__metric', `is-${item.tone}`]"
        >
          <span>{{ item.label }}</span>
          <strong>{{ item.value }}<em>{{ item.unit }}</em></strong>
        </article>
      </div>

      <div class="perf-panel__chart-wrap">
        <div ref="chartRef" class="perf-panel__chart" />
      </div>

    </div>
  </section>

  <button v-else type="button" class="perf-restore" @click="visible = true">
    显示性能面板
  </button>
</template>

<style scoped>
.perf-panel {
  position: relative;
  overflow: hidden;
  margin-top: 14px;
  border: 1px solid rgba(39, 216, 255, 0.22);
  border-radius: 16px;
  background:
    radial-gradient(circle at 0% 0%, rgba(39, 216, 255, 0.16), transparent 30%),
    linear-gradient(135deg, rgba(0, 61, 122, 0.16), rgba(0, 20, 43, 0.72));
  box-shadow: inset 0 0 28px rgba(39, 216, 255, 0.05), 0 18px 36px rgba(0, 0, 0, 0.16);
}

.perf-panel::after {
  content: "";
  position: absolute;
  inset: 0;
  pointer-events: none;
  background: linear-gradient(90deg, transparent, rgba(212, 175, 55, 0.08), transparent);
  transform: translateX(-70%) skewX(-16deg);
}

.perf-panel__header {
  position: relative;
  z-index: 1;
  display: grid;
  grid-template-columns: minmax(180px, 1fr) auto auto;
  align-items: center;
  gap: 16px;
  padding: 16px 18px;
  border-bottom: 1px solid rgba(39, 216, 255, 0.14);
}

.perf-panel__eyebrow {
  color: #d4af37;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.18em;
}

.perf-panel h3 {
  margin: 4px 0 0;
  color: #eaf4ff;
  font-size: 18px;
  letter-spacing: 0.12em;
}

.perf-panel__status {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: #8aa8c7;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
}

.perf-panel__status span {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  background: currentColor;
  box-shadow: 0 0 12px currentColor;
}

.perf-panel__status.is-live { color: #20c36b; }
.perf-panel__status.is-idle { color: #8aa8c7; }

.perf-panel__actions {
  display: inline-flex;
  gap: 8px;
}

.perf-panel__actions button,
.perf-restore {
  border: 1px solid rgba(39, 216, 255, 0.28);
  border-radius: 999px;
  background: rgba(0, 20, 43, 0.52);
  color: #27d8ff;
  cursor: pointer;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
}

.perf-panel__actions button {
  height: 28px;
  padding: 0 12px;
}

.perf-panel__actions button:hover,
.perf-restore:hover {
  border-color: #d4af37;
  color: #d4af37;
}

.perf-panel__body {
  position: relative;
  z-index: 1;
  display: grid;
  grid-template-columns: minmax(260px, 0.9fr) minmax(360px, 1.4fr);
  gap: 14px;
  padding: 16px 18px 18px;
}

.perf-panel__metrics {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.perf-panel__metric {
  min-height: 78px;
  padding: 12px;
  border: 1px solid rgba(39, 216, 255, 0.14);
  border-radius: 12px;
  background: rgba(0, 20, 43, 0.42);
}

.perf-panel__metric span {
  color: #8aa8c7;
  font-size: 12px;
  letter-spacing: 0.1em;
}

.perf-panel__metric strong {
  display: block;
  margin-top: 8px;
  color: #eaf4ff;
  font-family: Impact, "DIN Alternate", sans-serif;
  font-size: 32px;
  font-weight: 800;
  letter-spacing: 0.04em;
}

.perf-panel__metric em {
  margin-left: 4px;
  color: #8aa8c7;
  font-family: "PingFang SC", sans-serif;
  font-size: 12px;
  font-style: normal;
}

.perf-panel__metric.is-good strong { color: #20c36b; text-shadow: 0 0 16px rgba(32, 195, 107, 0.24); }
.perf-panel__metric.is-warning strong { color: #f97316; text-shadow: 0 0 16px rgba(249, 115, 22, 0.24); }
.perf-panel__metric.is-danger strong { color: #ff6b6b; text-shadow: 0 0 16px rgba(178, 34, 34, 0.28); }
.perf-panel__metric.is-idle strong { color: #eaf4ff; }

.perf-panel__chart-wrap {
  min-height: 180px;
  border: 1px solid rgba(39, 216, 255, 0.12);
  border-radius: 12px;
  background: rgba(0, 20, 43, 0.35);
}

.perf-panel__chart {
  width: 100%;
  height: 100%;
  min-height: 180px;
}

.perf-restore {
  margin-top: 14px;
  height: 34px;
  padding: 0 14px;
}

@media (max-width: 1180px) {
  .perf-panel__body {
    grid-template-columns: 1fr;
  }
}

@media (prefers-reduced-motion: reduce) {
  .perf-panel::after {
    display: none;
  }
}
</style>
