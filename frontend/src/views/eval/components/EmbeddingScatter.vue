<script setup lang="ts">
import { Search } from "@element-plus/icons-vue";
import { computed, nextTick, onMounted, ref, watch } from "vue";

import { useEchart, type ScreenEchartOption } from "@/views/screen/composables/useEchart";

interface ProjectionPoint {
  x: number;
  y: number;
  person_id?: number;
  name: string;
  role: string;
}

interface IdentityGroup {
  key: string;
  label: string;
  role: string;
  personId?: number;
  points: ProjectionPoint[];
}

const roleLabels: Record<string, string> = {
  student: "本科生",
  graduate: "研究生",
  teacher: "教师",
  staff: "职工",
  visitor: "访客",
};

const palette = [
  "#003D7A", "#20C36B", "#D4AF37", "#B22222", "#27D8FF",
  "#F97316", "#8B5CF6", "#14B8A6", "#E11D48", "#64748B",
];

const points = ref<ProjectionPoint[]>([]);
const loading = ref(false);
const error = ref("");
const activeRole = ref("all");
const searchText = ref("");

const identityGroups = computed(() => {
  const groups = new Map<string, IdentityGroup>();
  for (const point of points.value) {
    const label = point.name || "未命名";
    const key = point.person_id != null ? `person:${point.person_id}` : `name:${label}`;
    const group = groups.get(key) ?? {
      key,
      label,
      role: point.role || "unknown",
      personId: point.person_id,
      points: [],
    };
    group.points.push(point);
    groups.set(key, group);
  }
  return Array.from(groups.values());
});

const roleCounts = computed(() => {
  const counts = new Map<string, number>();
  for (const group of identityGroups.value) {
    counts.set(group.role, (counts.get(group.role) ?? 0) + 1);
  }
  const roleOrder = Object.keys(roleLabels);
  return Array.from(counts.entries())
    .map(([role, count]) => ({ role, count }))
    .sort((a, b) => {
      const ai = roleOrder.indexOf(a.role);
      const bi = roleOrder.indexOf(b.role);
      if (ai === -1 && bi === -1) return a.role.localeCompare(b.role);
      if (ai === -1) return 1;
      if (bi === -1) return -1;
      return ai - bi;
    });
});

const normalizedSearch = computed(() => searchText.value.trim().toLowerCase());
const hasFilter = computed(() => activeRole.value !== "all" || normalizedSearch.value !== "");
const totalIdentityCount = computed(() => identityGroups.value.length);

const filteredIdentityGroups = computed(() => {
  const query = normalizedSearch.value;
  return identityGroups.value.filter((group) => {
    if (activeRole.value !== "all" && group.role !== activeRole.value) return false;
    if (!query) return true;
    const roleLabel = roleLabels[group.role] ?? group.role;
    const haystack = [
      group.label,
      group.key,
      group.personId,
      roleLabel,
      group.role,
    ].join(" ").toLowerCase();
    return haystack.includes(query);
  });
});

const visiblePoints = computed(() => filteredIdentityGroups.value.flatMap((group) => group.points));
const summaryCount = computed(() => (hasFilter.value ? visiblePoints.value.length : points.value.length));
const summaryLabel = computed(() => (hasFilter.value ? `筛选点 / ${points.value.length}` : "向量点"));

const option = computed<ScreenEchartOption>(() => ({
  backgroundColor: "transparent",
  color: palette,
  animationDuration: 900,
  animationEasing: "cubicOut",
  grid: { left: 34, right: 34, top: 42, bottom: 44, containLabel: true },
  legend: {
    type: "scroll",
    top: 0,
    right: 8,
    icon: "circle",
    textStyle: { color: "#516071", fontSize: 12 },
  },
  tooltip: {
    trigger: "item",
    borderColor: "rgba(0,61,122,0.18)",
    backgroundColor: "rgba(255,255,255,0.96)",
    textStyle: { color: "#172033" },
    formatter(params: { data?: unknown; seriesName?: string }) {
      const item = params.data as [number, number, string, string] | undefined;
      if (!item) return "";
      const [x, y, name, role] = item;
      return [
        `<strong>${name}</strong>`,
        `身份：${params.seriesName || name}`,
        `角色：${roleLabels[role] ?? role}`,
        `坐标：(${Number(x).toFixed(3)}, ${Number(y).toFixed(3)})`,
      ].join("<br/>");
    },
  },
  xAxis: {
    type: "value",
    name: "Projection X",
    min: -1.08,
    max: 1.08,
    nameTextStyle: { color: "#7A8798" },
    axisLine: { lineStyle: { color: "#D9E2EC" } },
    axisLabel: { color: "#7A8798", fontSize: 11 },
    splitLine: { lineStyle: { color: "rgba(0,61,122,0.08)" } },
  },
  yAxis: {
    type: "value",
    name: "Projection Y",
    min: -1.08,
    max: 1.08,
    nameTextStyle: { color: "#7A8798" },
    axisLine: { lineStyle: { color: "#D9E2EC" } },
    axisLabel: { color: "#7A8798", fontSize: 11 },
    splitLine: { lineStyle: { color: "rgba(0,61,122,0.08)" } },
  },
  series: filteredIdentityGroups.value.map((group, index) => ({
    name: group.label,
    type: "scatter",
    symbolSize(value: unknown) {
      const role = Array.isArray(value) ? String(value[3] ?? "") : "";
      return role === "teacher" || role === "staff" ? 15 : 12;
    },
    emphasis: {
      focus: "series",
      scale: 1.45,
      itemStyle: {
        borderColor: "#D4AF37",
        borderWidth: 2,
        shadowBlur: 16,
        shadowColor: "rgba(0,61,122,0.28)",
      },
    },
    itemStyle: {
      color: palette[index % palette.length],
      opacity: 0.86,
      borderColor: "rgba(255,255,255,0.88)",
      borderWidth: 1,
    },
    data: group.points.map((point) => [point.x, point.y, point.name, point.role]),
  })),
}));

const { chartRef, chart, resize, setOption } = useEchart(option);

function refreshChartWithReplacement() {
  // ECharts merges series by index by default; clear first so filters really remove old identities.
  chart.value?.clear();
  void nextTick(() => {
    setOption();
    resize();
  });
}

async function loadProjection() {
  loading.value = true;
  error.value = "";
  try {
    const response = await fetch(`/eval/embedding_2d.json?t=${Date.now()}`);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json() as ProjectionPoint[];
    points.value = data.filter((item) => Number.isFinite(item.x) && Number.isFinite(item.y));
  } catch (err) {
    points.value = [];
    error.value = err instanceof Error ? err.message : String(err);
  } finally {
    loading.value = false;
    requestAnimationFrame(resize);
  }
}

onMounted(loadProjection);

watch([activeRole, normalizedSearch], refreshChartWithReplacement);
</script>

<template>
  <section class="embedding-card">
    <header class="card-head">
      <div>
        <span class="eyebrow">512-D EdgeFace Embedding · 2D Projection</span>
        <h2>嵌入空间投影</h2>
        <p>同一身份的多张人脸应在二维空间内相互靠近，不同身份之间呈现分离趋势。</p>
      </div>
      <div class="head-tools">
        <el-input
          v-model="searchText"
          class="search-input"
          :prefix-icon="Search"
          clearable
          placeholder="搜索姓名 / ID / 角色"
        />
        <div class="summary">
          <strong>{{ summaryCount }}</strong>
          <span>{{ summaryLabel }}</span>
        </div>
      </div>
    </header>

    <div class="meta-row">
      <button
        type="button"
        class="filter-chip"
        :class="{ active: activeRole === 'all' }"
        @click="activeRole = 'all'"
      >
        <span>身份</span>
        <strong>{{ totalIdentityCount }}</strong>
      </button>
      <button
        v-for="item in roleCounts"
        :key="item.role"
        type="button"
        class="filter-chip"
        :class="{ active: activeRole === item.role }"
        @click="activeRole = item.role"
      >
        <span>{{ roleLabels[item.role] ?? item.role }}</span>
        <strong>{{ item.count }}</strong>
      </button>
      <el-button size="small" plain :loading="loading" @click="loadProjection">刷新投影</el-button>
    </div>

    <p v-if="hasFilter" class="filter-note">
      当前显示 {{ filteredIdentityGroups.length }} 个身份 / {{ visiblePoints.length }} 个向量点
    </p>

    <div class="chart-shell">
      <div ref="chartRef" class="chart" />
      <div v-if="loading" class="state-mask">加载嵌入投影…</div>
      <div v-else-if="error" class="state-mask is-error">
        <strong>未找到投影数据</strong>
        <span>请先运行：python app/scripts/export_embedding_projection.py</span>
        <em>{{ error }}</em>
      </div>
      <div v-else-if="!points.length" class="state-mask is-error">
        <strong>暂无投影点</strong>
        <span>请确认 MySQL face_embeddings 与 FAISS ids 一致。</span>
      </div>
      <div v-else-if="!visiblePoints.length" class="state-mask">
        <strong>没有匹配结果</strong>
        <span>请调整角色筛选或搜索关键词。</span>
        <button type="button" @click="activeRole = 'all'; searchText = ''">清除筛选</button>
      </div>
    </div>
  </section>
</template>

<style scoped>
.embedding-card {
  position: relative;
  overflow: hidden;
  border: 1px solid rgba(0, 61, 122, 0.1);
  border-radius: 24px;
  padding: 22px;
  background:
    radial-gradient(circle at 12% 0%, rgba(212, 175, 55, 0.16), transparent 34%),
    radial-gradient(circle at 88% 12%, rgba(0, 61, 122, 0.14), transparent 30%),
    rgba(255, 255, 255, 0.86);
  box-shadow: 0 18px 48px rgba(0, 35, 76, 0.08);
}

.card-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18px;
}

.head-tools {
  display: flex;
  align-items: stretch;
  gap: 12px;
}

.search-input {
  width: clamp(220px, 24vw, 340px);
  align-self: center;
}

.search-input :deep(.el-input__wrapper) {
  min-height: 42px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.9);
  box-shadow:
    inset 0 0 0 1px rgba(0, 61, 122, 0.08),
    0 10px 24px rgba(0, 61, 122, 0.08);
}

.eyebrow {
  color: #003d7a;
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

h2 {
  margin: 6px 0 6px;
  color: #172033;
  font-size: clamp(24px, 3vw, 34px);
  letter-spacing: -0.04em;
}

p {
  max-width: 720px;
  margin: 0;
  color: #637083;
  line-height: 1.65;
}

.summary {
  min-width: 108px;
  border-radius: 18px;
  padding: 14px 16px;
  text-align: right;
  color: #fff;
  background: linear-gradient(145deg, #003d7a, #0f5fa8);
  box-shadow: 0 14px 30px rgba(0, 61, 122, 0.2);
}

.summary strong {
  display: block;
  font-size: 30px;
  line-height: 1;
}

.summary span {
  color: rgba(255, 255, 255, 0.72);
  font-size: 12px;
}

.meta-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin: 18px 0 16px;
}

.filter-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-height: 32px;
  border: 1px solid rgba(0, 61, 122, 0.14);
  border-radius: 999px;
  padding: 0 12px;
  color: #003d7a;
  font-size: 13px;
  font-weight: 800;
  background: rgba(255, 255, 255, 0.74);
  box-shadow: 0 8px 18px rgba(0, 61, 122, 0.06);
  cursor: pointer;
  transition: transform 0.18s ease, border-color 0.18s ease, background 0.18s ease, color 0.18s ease;
}

.filter-chip:hover {
  transform: translateY(-1px);
  border-color: rgba(0, 61, 122, 0.32);
  background: rgba(255, 255, 255, 0.95);
}

.filter-chip.active {
  color: #fff;
  border-color: transparent;
  background: linear-gradient(135deg, #003d7a, #0f5fa8);
}

.filter-chip strong {
  font-size: 14px;
  font-variant-numeric: tabular-nums;
}

.filter-note {
  margin: -6px 0 14px;
  color: #637083;
  font-size: 13px;
  font-weight: 700;
}

.chart-shell {
  position: relative;
  min-height: 560px;
  overflow: hidden;
  border: 1px solid rgba(0, 61, 122, 0.08);
  border-radius: 20px;
  background:
    linear-gradient(rgba(0, 61, 122, 0.035) 1px, transparent 1px),
    linear-gradient(90deg, rgba(0, 61, 122, 0.035) 1px, transparent 1px),
    linear-gradient(180deg, #ffffff, #f7fbff);
  background-size: 32px 32px;
}

.chart {
  width: 100%;
  height: 560px;
}

.state-mask {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 28px;
  color: #637083;
  text-align: center;
  background: rgba(255, 255, 255, 0.78);
  backdrop-filter: blur(8px);
}

.state-mask strong {
  color: #172033;
  font-size: 18px;
}

.state-mask em {
  max-width: 520px;
  color: #b22222;
  font-size: 12px;
  font-style: normal;
  word-break: break-word;
}

.state-mask.is-error {
  color: #7a4d18;
}

.state-mask button {
  min-height: 34px;
  border: 0;
  border-radius: 999px;
  padding: 0 14px;
  color: #fff;
  font-weight: 800;
  background: #003d7a;
  cursor: pointer;
}

@media (max-width: 720px) {
  .card-head {
    flex-direction: column;
  }

  .head-tools {
    width: 100%;
    flex-direction: column;
  }

  .search-input {
    width: 100%;
  }

  .summary {
    width: 100%;
    text-align: left;
  }

  .chart-shell,
  .chart {
    min-height: 460px;
    height: 460px;
  }
}
</style>
