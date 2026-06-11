<script setup lang="ts">
import VChart from "vue-echarts";
import { use } from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import { BarChart, LineChart, PieChart } from "echarts/charts";
import {
  GridComponent, LegendComponent, TitleComponent, TooltipComponent,
} from "echarts/components";

import { systemApi } from "@/api/system";
import type { DashboardOut } from "@/api/types";
import PageHeader from "@/components/common/PageHeader.vue";
import StatCard from "@/components/common/StatCard.vue";

use([
  CanvasRenderer, BarChart, LineChart, PieChart,
  GridComponent, LegendComponent, TitleComponent, TooltipComponent,
]);

const data = ref<DashboardOut | null>(null);
const loading = ref(false);

async function load() {
  loading.value = true;
  try { data.value = await systemApi.dashboard(); }
  finally { loading.value = false; }
}
onMounted(load);

const decisionLabels: Record<string, string> = {
  granted: "通行", rejected: "未识别", spoof: "活体拒", no_face: "无脸",
};

/* ===== ECharts options ===== */
const lineOption = computed(() => ({
  grid: { left: 44, right: 16, top: 32, bottom: 24 },
  tooltip: { trigger: "axis", borderColor: "#E5E7EB", textStyle: { fontSize: 13 } },
  xAxis: {
    type: "category", boundaryGap: false,
    data: (data.value?.by_hour_line ?? []).map((p) => p.hour.slice(11, 16)),
    axisLine: { lineStyle: { color: "#E5E7EB" } },
    axisLabel: { color: "#8C8C8C", fontSize: 11 },
  },
  yAxis: {
    type: "value",
    splitLine: { lineStyle: { color: "#EEF1F5" } },
    axisLabel: { color: "#8C8C8C", fontSize: 11 },
  },
  series: [{
    name: "通行数", type: "line", smooth: true,
    symbol: "circle", symbolSize: 6,
    lineStyle: { width: 2.5, color: "#003D7A" },
    itemStyle: { color: "#003D7A" },
    areaStyle: {
      color: {
        type: "linear", x: 0, y: 0, x2: 0, y2: 1,
        colorStops: [
          { offset: 0, color: "rgba(0,61,122,0.28)" },
          { offset: 1, color: "rgba(0,61,122,0.01)" },
        ],
      },
    },
    data: (data.value?.by_hour_line ?? []).map((p) => p.total),
  }],
}));

const facultyBarOption = computed(() => ({
  grid: { left: 110, right: 24, top: 18, bottom: 18 },
  tooltip: { trigger: "axis" },
  xAxis: {
    type: "value",
    splitLine: { lineStyle: { color: "#EEF1F5" } },
    axisLabel: { color: "#8C8C8C", fontSize: 11 },
  },
  yAxis: {
    type: "category", inverse: true,
    data: (data.value?.by_faculty_bar ?? []).map((p) => p.faculty),
    axisLine: { show: false }, axisTick: { show: false },
    axisLabel: { color: "#595959", fontSize: 12 },
  },
  series: [{
    type: "bar", barWidth: 14,
    itemStyle: {
      borderRadius: [0, 6, 6, 0],
      color: { type: "linear", x: 0, y: 0, x2: 1, y2: 0,
        colorStops: [
          { offset: 0, color: "#1565C0" },
          { offset: 1, color: "#003D7A" },
        ],
      },
    },
    data: (data.value?.by_faculty_bar ?? []).map((p) => p.total),
  }],
}));

const pieOption = computed(() => {
  const palette: Record<string, string> = {
    granted: "#52C41A", rejected: "#F5222D", spoof: "#FAAD14", no_face: "#8C8C8C",
  };
  const items = (data.value?.by_decision_pie ?? []).map((p) => ({
    name: decisionLabels[p.name] ?? p.name, value: p.value,
    itemStyle: { color: palette[p.name] ?? "#8C8C8C" },
  }));
  return {
    tooltip: { trigger: "item" },
    legend: { bottom: 0, icon: "circle", textStyle: { color: "#595959" } },
    series: [{
      type: "pie", radius: ["50%", "74%"], center: ["50%", "44%"],
      avoidLabelOverlap: true, label: { show: false }, labelLine: { show: false },
      data: items,
    }],
  };
});
</script>

<template>
  <div class="dashboard">
    <PageHeader
      title="西小卫 · 仪表盘"
      subtitle="西南大学校园人脸识别门禁系统"
    >
      <template #actions>
        <el-button @click="load" :loading="loading" plain>刷新</el-button>
      </template>
    </PageHeader>

    <!-- KPI 卡片：借鉴 art-design-pro 分析页 today-sales 四列布局 -->
    <div class="kpi-grid">
      <StatCard label="今日通行" :value="data?.today?.total ?? 0" icon="Promotion" tone="blue"
        :hint="`本周累计 ${data?.week?.total ?? 0}`" :delta="data?.week?.total ? '活跃' : undefined" delta-up />
      <StatCard label="通行成功" :value="data?.today?.granted ?? 0" icon="CircleCheckFilled" tone="green"
        :hint="data?.today?.total ? `占比 ${((data.today.granted / data.today.total) * 100).toFixed(1)}%` : '暂无数据'" />
      <StatCard label="活体拒绝" :value="data?.today?.spoof ?? 0" icon="WarningFilled" tone="red"
        hint="MiniFAS 判别攻击" />
      <StatCard label="门禁在线" :value="`${data?.gates_online ?? 0}/${data?.gates_total ?? 0}`"
        icon="School" tone="cyan" hint="北碚校区七门" />
      <StatCard label="注册人员" :value="data?.persons_total ?? 0" icon="UserFilled" tone="blue"
        :hint="`激活 ${data?.persons_active ?? 0}`" />
      <StatCard label="人脸样本" :value="data?.embedding_total ?? 0" icon="Picture" tone="gold"
        hint="FAISS 向量库" />
    </div>

    <!-- 图表区 -->
    <div class="chart-grid">
      <div class="swu-card chart-line">
        <div class="swu-card-header">
          <div class="title"><h4>24 小时通行趋势</h4></div>
          <el-tag size="small" effect="plain" type="info">实时</el-tag>
        </div>
        <VChart :option="lineOption" autoresize style="height: 280px;" />
      </div>

      <div class="swu-card chart-pie">
        <div class="swu-card-header">
          <div class="title"><h4>今日决策分布</h4></div>
        </div>
        <VChart :option="pieOption" autoresize style="height: 280px;" />
      </div>

      <div class="swu-card chart-bar">
        <div class="swu-card-header">
          <div class="title"><h4>各学部通行 TOP10</h4></div>
          <span style="font-size:12px;color:var(--swu-text-3)">今日</span>
        </div>
        <VChart :option="facultyBarOption" autoresize style="height: 320px;" />
      </div>
    </div>

    <!-- 最近通行 -->
    <div class="swu-card">
      <div class="swu-card-header">
        <div class="title"><h4>最近通行事件</h4></div>
        <router-link to="/access-logs" style="font-size:12px;color:var(--swu-blue);text-decoration:none">查看全部 →</router-link>
      </div>
      <el-table :data="data?.recent_logs ?? []" stripe size="small" style="width:100%"
        :header-cell-style="{ background: 'var(--swu-bg)', color: 'var(--swu-text-2)', fontWeight: 600 }">
        <el-table-column prop="ts" label="时间" width="180">
          <template #default="{ row }">{{ row.ts.replace('T', ' ').slice(0, 19) }}</template>
        </el-table-column>
        <el-table-column prop="gate_name" label="门禁" min-width="180" />
        <el-table-column prop="person_external_id" label="学号/工号" width="170" />
        <el-table-column prop="person_name" label="姓名" width="120" />
        <el-table-column prop="decision" label="决策" width="100">
          <template #default="{ row }">
            <el-tag :type="row.decision === 'granted' ? 'success' : row.decision === 'spoof' ? 'warning' : row.decision === 'rejected' ? 'danger' : 'info'"
              size="small" effect="light">
              {{ decisionLabels[row.decision] || row.decision }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="score" label="相似度" width="100">
          <template #default="{ row }">{{ row.score == null ? '—' : row.score.toFixed(3) }}</template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>

<style scoped>
.dashboard {
  display: flex; flex-direction: column; gap: 16px;
  animation: slide-up 0.4s cubic-bezier(0.16, 1, 0.3, 1);
}

.kpi-grid {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 14px;
}
@media (max-width: 1400px) { .kpi-grid { grid-template-columns: repeat(3, 1fr); } }
@media (max-width: 720px)  { .kpi-grid { grid-template-columns: repeat(2, 1fr); } }

.chart-grid {
  display: grid;
  grid-template-columns: 2fr 1fr;
  grid-template-rows: auto auto;
  gap: 14px;
}
.chart-line { grid-column: 1; grid-row: 1; }
.chart-pie  { grid-column: 2; grid-row: 1; }
.chart-bar  { grid-column: 1 / -1; grid-row: 2; }
@media (max-width: 1024px) {
  .chart-grid { grid-template-columns: 1fr; }
  .chart-line, .chart-pie, .chart-bar { grid-column: 1; grid-row: auto; }
}

@keyframes slide-up {
  from { opacity: 0; transform: translateY(8px); }
  to   { opacity: 1; transform: translateY(0); }
}
</style>
