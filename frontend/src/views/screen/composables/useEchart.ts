import { BarChart, EffectScatterChart, LineChart, PieChart, ScatterChart } from "echarts/charts";
import {
  GraphicComponent,
  GridComponent,
  LegendComponent,
  TitleComponent,
  TooltipComponent,
} from "echarts/components";
import { init, use } from "echarts/core";
import type { EChartsCoreOption, EChartsType } from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import { nextTick, onActivated, onBeforeUnmount, onDeactivated, onMounted, ref, shallowRef, unref, watch, type Ref } from "vue";

import { screenMotion } from "@/styles/motion-tokens";

let registered = false;

function registerEcharts() {
  if (registered) return;
  use([
    CanvasRenderer,
    LineChart,
    BarChart,
    PieChart,
    ScatterChart,
    EffectScatterChart,
    GridComponent,
    TooltipComponent,
    LegendComponent,
    TitleComponent,
    GraphicComponent,
  ]);
  registered = true;
}

export type ScreenEchartOption = EChartsCoreOption;

export function useEchart(option: Ref<ScreenEchartOption> | (() => ScreenEchartOption)) {
  registerEcharts();

  const chartRef = ref<HTMLDivElement | null>(null);
  const chart = shallowRef<EChartsType | null>(null);
  let resizeTimer: number | null = null;
  let listening = false;

  function getOption() {
    return typeof option === "function" ? option() : unref(option);
  }

  function resize() {
    if (resizeTimer !== null) clearTimeout(resizeTimer);
    resizeTimer = window.setTimeout(() => {
      chart.value?.resize();
      resizeTimer = null;
    }, screenMotion.resizeDebounceMs);
  }

  function bindResize() {
    if (listening) return;
    window.addEventListener("resize", resize);
    listening = true;
  }

  function unbindResize() {
    if (resizeTimer !== null) {
      clearTimeout(resizeTimer);
      resizeTimer = null;
    }
    if (!listening) return;
    window.removeEventListener("resize", resize);
    listening = false;
  }

  function setOption() {
    if (!chart.value) return;
    chart.value.setOption(getOption(), { notMerge: false, lazyUpdate: true });
  }

  async function mountChart() {
    await nextTick();
    if (!chartRef.value || chart.value) return;
    chart.value = init(chartRef.value, undefined, { renderer: "canvas" });
    setOption();
    bindResize();
  }

  function disposeChart() {
    unbindResize();
    chart.value?.dispose();
    chart.value = null;
  }

  watch(
    () => getOption(),
    () => setOption(),
    { deep: true, flush: "post" },
  );

  onMounted(mountChart);
  onActivated(mountChart);
  onDeactivated(disposeChart);
  onBeforeUnmount(disposeChart);

  return {
    chartRef,
    chart,
    resize,
    setOption,
    disposeChart,
  };
}
