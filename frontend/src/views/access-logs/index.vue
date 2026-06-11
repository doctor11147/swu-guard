<script setup lang="ts">
/** 通行记录 · 多维筛选 + 表格 + CSV 导出。 */
import { Download, Refresh, Search } from "@element-plus/icons-vue";
import dayjs from "dayjs";

import { logsApi, type LogQuery } from "@/api/access-logs";
import { gatesApi } from "@/api/gates";
import type { AccessLogOut, GateOut } from "@/api/types";
import DataCard from "@/components/common/DataCard.vue";
import FilterBar from "@/components/common/FilterBar.vue";
import PageHeader from "@/components/common/PageHeader.vue";

const rows = ref<AccessLogOut[]>([]);
const total = ref(0);
const loading = ref(false);
const gates = ref<GateOut[]>([]);
const stats = ref<{
  today_total: number; week_total: number;
  by_decision: Record<string, number>;
} | null>(null);

const range = ref<[Date, Date] | null>(null);
const query = reactive<LogQuery>({
  decision: "", gate_id: undefined, page: 1, page_size: 20,
});

const decisionOptions = [
  { value: "granted",  label: "通行" },
  { value: "rejected", label: "未识别" },
  { value: "spoof",    label: "活体拒" },
  { value: "no_face",  label: "无脸" },
];

function decisionTagType(d: string) {
  return (({ granted: "success", rejected: "danger", spoof: "warning",
             no_face: "info" } as Record<string, string>)[d] || "");
}
function decisionLabel(d: string) {
  return decisionOptions.find((o) => o.value === d)?.label ?? d;
}

async function load() {
  loading.value = true;
  try {
    const params: LogQuery = { ...query } as LogQuery;
    if (range.value && range.value.length === 2) {
      params.from = dayjs(range.value[0]).format("YYYY-MM-DDTHH:mm:ss");
      params.to = dayjs(range.value[1]).format("YYYY-MM-DDTHH:mm:ss");
    }
    (Object.keys(params) as Array<keyof LogQuery>).forEach((k) => {
      if (params[k] === "" || params[k] === undefined) delete params[k];
    });
    const r = await logsApi.list(params);
    rows.value = r.items;
    total.value = r.total;
  } finally {
    loading.value = false;
  }
}

async function loadStats() {
  try {
    const s = await logsApi.stats();
    stats.value = {
      today_total: s.today_total,
      week_total: s.week_total,
      by_decision: s.by_decision,
    };
  } catch { /* ignore */ }
}

async function loadGates() {
  try { gates.value = await gatesApi.list(); } catch { /* ignore */ }
}

onMounted(async () => {
  await Promise.all([loadGates(), loadStats()]);
  await load();
});

function onSearch() { query.page = 1; load(); }
function onPageChange(p: number) { query.page = p; load(); }
function reset() {
  range.value = null;
  query.decision = "";
  query.gate_id = undefined;
  query.page = 1;
  load();
}

function exportCsv() {
  const params: LogQuery = { ...query } as LogQuery;
  if (range.value && range.value.length === 2) {
    params.from = dayjs(range.value[0]).format("YYYY-MM-DDTHH:mm:ss");
    params.to = dayjs(range.value[1]).format("YYYY-MM-DDTHH:mm:ss");
  }
  window.open(logsApi.exportCsvUrl(params), "_blank");
}

const quick = (key: "today" | "week" | "month") => {
  const now = dayjs();
  if (key === "today") range.value = [now.startOf("day").toDate(), now.toDate()];
  else if (key === "week") range.value = [now.subtract(7, "day").toDate(), now.toDate()];
  else if (key === "month") range.value = [now.subtract(30, "day").toDate(), now.toDate()];
  onSearch();
};
</script>

<template>
  <div>
    <PageHeader title="通行记录" subtitle="所有识别事件 · 支持按时间/决策/门禁筛选 + CSV 导出">
      <template #actions>
        <el-button :icon="Refresh" circle title="刷新" @click="() => { loadStats(); load(); }" />
        <el-button :icon="Download" type="primary" @click="exportCsv">导出 CSV</el-button>
      </template>
    </PageHeader>

    <div class="mini-stats" v-if="stats">
      <div class="mini">
        <div class="mini-label">今日通行</div>
        <div class="mini-value">{{ stats.today_total }}</div>
      </div>
      <div class="mini">
        <div class="mini-label">7 日累计</div>
        <div class="mini-value">{{ stats.week_total }}</div>
      </div>
      <div class="mini">
        <div class="mini-label">今日成功</div>
        <div class="mini-value text-green">{{ stats.by_decision.granted ?? 0 }}</div>
      </div>
      <div class="mini">
        <div class="mini-label">今日活体拒</div>
        <div class="mini-value text-orange">{{ stats.by_decision.spoof ?? 0 }}</div>
      </div>
      <div class="mini">
        <div class="mini-label">今日未识别</div>
        <div class="mini-value text-red">{{ stats.by_decision.rejected ?? 0 }}</div>
      </div>
    </div>

    <FilterBar>
      <el-date-picker
        v-model="range" type="datetimerange" unlink-panels
        start-placeholder="开始时间" end-placeholder="结束时间"
        format="YYYY-MM-DD HH:mm" value-format="YYYY-MM-DDTHH:mm:ss"
        style="width: 360px"
      />
      <el-select v-model="query.decision" placeholder="决策" clearable style="width: 140px" @change="onSearch">
        <el-option v-for="o in decisionOptions" :key="o.value" :label="o.label" :value="o.value" />
      </el-select>
      <el-select v-model="query.gate_id" placeholder="门禁" clearable filterable style="width: 220px" @change="onSearch">
        <el-option v-for="g in gates" :key="g.id" :label="g.name" :value="g.id" />
      </el-select>
      <div class="quick">
        <el-button size="small" link type="primary" @click="quick('today')">今日</el-button>
        <el-button size="small" link type="primary" @click="quick('week')">近 7 日</el-button>
        <el-button size="small" link type="primary" @click="quick('month')">近 30 日</el-button>
      </div>
      <template #actions>
        <el-button type="primary" :icon="Search" @click="onSearch">查询</el-button>
        <el-button @click="reset">重置</el-button>
      </template>
    </FilterBar>

    <DataCard>
      <el-table
        :data="rows" v-loading="loading" stripe
        :header-cell-style="{ background: 'var(--swu-blue-50)', color: 'var(--swu-text)', fontWeight: 600 }"
      >
        <el-table-column type="index" label="#" width="56" />
        <el-table-column label="时间" width="180">
          <template #default="{ row }">
            <div class="mono">{{ row.ts.replace('T', ' ').slice(0, 19) }}</div>
          </template>
        </el-table-column>
        <el-table-column prop="gate_name" label="门禁" min-width="180" />
        <el-table-column prop="person_external_id" label="学号/工号" width="170">
          <template #default="{ row }">
            <span class="mono">{{ row.person_external_id || "—" }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="person_name" label="姓名" width="120" />
        <el-table-column label="决策" width="100">
          <template #default="{ row }">
            <el-tag :type="decisionTagType(row.decision) as any" size="small">
              {{ decisionLabel(row.decision) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="相似度" width="110">
          <template #default="{ row }">
            <span v-if="row.score == null">—</span>
            <span v-else :class="row.score > 0.4 ? 'text-green' : 'text-red'">
              {{ row.score.toFixed(3) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="活体分" width="110">
          <template #default="{ row }">
            <span v-if="row.spoof_score == null">—</span>
            <span v-else :class="row.spoof_score >= 0.85 ? 'text-green' : 'text-orange'">
              {{ row.spoof_score.toFixed(3) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="详情" min-width="180">
          <template #default="{ row }">
            <span class="dim">{{ row.detail || "—" }}</span>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagi">
        <el-pagination
          background
          :current-page="query.page" :page-size="query.page_size" :total="total"
          :page-sizes="[20, 50, 100, 200]"
          layout="total, sizes, prev, pager, next, jumper"
          @current-change="onPageChange"
          @size-change="(s: number) => { query.page_size = s; query.page = 1; load(); }"
        />
      </div>
    </DataCard>
  </div>
</template>

<style scoped>
.mini-stats {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 12px;
  margin-bottom: 14px;
}
@media (max-width: 880px) { .mini-stats { grid-template-columns: repeat(2, 1fr); } }

.mini {
  background: var(--swu-bg-elev);
  border: 1px solid var(--swu-border);
  border-radius: 10px;
  padding: 14px 16px;
}
.mini-label { font-size: 12px; color: var(--swu-text-3); }
.mini-value {
  margin-top: 4px;
  font-size: 22px; font-weight: 600;
  color: var(--swu-text);
  font-variant-numeric: tabular-nums;
}

.text-green  { color: var(--swu-success); }
.text-orange { color: var(--swu-warning); }
.text-red    { color: var(--swu-danger); }
.mono { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 13px; }
.dim { color: var(--swu-text-3); font-size: 12px; }

.quick { display: flex; gap: 4px; }
.pagi { display: flex; justify-content: flex-end; padding: 14px 4px 2px; }
</style>
