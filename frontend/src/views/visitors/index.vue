<script setup lang="ts">
/** 访客审核 · 管理员 / 门卫审批访客预约。 */
import { Check, Close, Refresh, Search } from "@element-plus/icons-vue";
import { ElMessage, ElMessageBox } from "element-plus";
import dayjs from "dayjs";

import {
  visitorsApi,
  type AppointmentOut,
  type AppointmentQuery,
} from "@/api/visitors";
import DataCard from "@/components/common/DataCard.vue";
import FilterBar from "@/components/common/FilterBar.vue";
import PageHeader from "@/components/common/PageHeader.vue";

const slotOptions = [
  { value: 0, label: "00:00-04:00" },
  { value: 1, label: "04:00-08:00" },
  { value: 2, label: "08:00-12:00" },
  { value: 3, label: "12:00-16:00" },
  { value: 4, label: "16:00-20:00" },
  { value: 5, label: "20:00-24:00" },
];

const statusOptions: Array<{ value: AppointmentOut["status"] | ""; label: string }> = [
  { value: "", label: "全部状态" },
  { value: "pending", label: "待审批" },
  { value: "approved", label: "已通过" },
  { value: "rejected", label: "已拒绝" },
  { value: "expired", label: "已过期" },
  { value: "cancelled", label: "已取消" },
];

const rows = ref<AppointmentOut[]>([]);
const total = ref(0);
const loading = ref(false);

const query = reactive<AppointmentQuery>({
  status: "pending",
  date: "",
  page: 1,
  page_size: 20,
});

const pageStats = computed(() => ({
  pending: rows.value.filter((r) => r.status === "pending").length,
  approved: rows.value.filter((r) => r.status === "approved").length,
  rejected: rows.value.filter((r) => r.status === "rejected").length,
  total: rows.value.length,
}));

function cleanQuery(): AppointmentQuery {
  const params: AppointmentQuery = { ...query };
  (Object.keys(params) as Array<keyof AppointmentQuery>).forEach((k) => {
    if (params[k] === "" || params[k] === undefined || params[k] === null) {
      delete params[k];
    }
  });
  return params;
}

async function load() {
  loading.value = true;
  try {
    const r = await visitorsApi.listAppointments(cleanQuery());
    rows.value = r.items;
    total.value = r.total;
  } finally {
    loading.value = false;
  }
}

onMounted(load);

function onSearch() {
  query.page = 1;
  load();
}

function reset() {
  Object.assign(query, {
    status: "pending",
    date: "",
    page: 1,
    page_size: 20,
  });
  load();
}

function onPageChange(page: number) {
  query.page = page;
  load();
}

function setToday() {
  query.date = dayjs().format("YYYY-MM-DD");
  onSearch();
}

function slotLabel(slot: number) {
  return slotOptions.find((s) => s.value === slot)?.label ?? `时段 ${slot}`;
}

function statusLabel(status: AppointmentOut["status"]) {
  return statusOptions.find((s) => s.value === status)?.label ?? status;
}

type TagType = "primary" | "success" | "warning" | "info" | "danger";
function statusType(status: AppointmentOut["status"]): TagType {
  return ({
    pending: "warning",
    approved: "success",
    rejected: "danger",
    expired: "info",
    cancelled: "info",
  } as Record<AppointmentOut["status"], TagType>)[status];
}

function formatTime(value: string | null) {
  return value ? dayjs(value).format("YYYY-MM-DD HH:mm") : "—";
}

function isCrossDay(row: AppointmentOut) {
  return row.arrival_date !== row.departure_date;
}

function canReview(row: AppointmentOut) {
  return row.status === "pending";
}

function canCancel(row: AppointmentOut) {
  return row.status === "pending" || row.status === "approved";
}

async function approve(row: AppointmentOut) {
  try {
    await ElMessageBox.confirm(
      `确认通过 ${row.visitor_name} 的访客预约？通过后该访客可在预约窗口内刷脸通行。`,
      "通过预约",
      { type: "success", confirmButtonText: "通过", cancelButtonText: "取消" },
    );
  } catch {
    return;
  }
  await visitorsApi.reviewAppointment(row.id, { action: "approve" });
  ElMessage.success("预约已通过");
  await load();
}

async function reject(row: AppointmentOut) {
  let reason = "";
  try {
    const out = await ElMessageBox.prompt(
      `请输入拒绝 ${row.visitor_name} 预约的理由`,
      "拒绝预约",
      {
        type: "warning",
        inputType: "textarea",
        inputPlaceholder: "例如：来访信息不完整 / 时间窗口不合规",
        inputValidator: (value) => !!String(value || "").trim(),
        inputErrorMessage: "拒绝预约必须填写理由",
        confirmButtonText: "拒绝",
        cancelButtonText: "取消",
      },
    );
    reason = String(out.value || "").trim();
  } catch {
    return;
  }
  await visitorsApi.reviewAppointment(row.id, { action: "reject", reason });
  ElMessage.success("预约已拒绝");
  await load();
}

async function cancel(row: AppointmentOut) {
  try {
    await ElMessageBox.confirm(
      `确认取消 ${row.visitor_name} 的访客预约？`,
      "取消预约",
      { type: "warning", confirmButtonText: "取消预约", cancelButtonText: "返回" },
    );
  } catch {
    return;
  }
  await visitorsApi.cancelAppointment(row.id);
  ElMessage.success("预约已取消");
  await load();
}
</script>

<template>
  <div>
    <PageHeader title="访客审核" subtitle="访客预约审批 / 跨天时间窗 / 刷脸通行授权">
      <template #actions>
        <el-button :icon="Refresh" circle title="刷新" @click="load" />
      </template>
    </PageHeader>

    <div class="mini-stats">
      <div class="mini">
        <div class="mini-label">当前页记录</div>
        <div class="mini-value">{{ pageStats.total }}</div>
      </div>
      <div class="mini">
        <div class="mini-label">待审批</div>
        <div class="mini-value text-orange">{{ pageStats.pending }}</div>
      </div>
      <div class="mini">
        <div class="mini-label">已通过</div>
        <div class="mini-value text-green">{{ pageStats.approved }}</div>
      </div>
      <div class="mini">
        <div class="mini-label">已拒绝</div>
        <div class="mini-value text-red">{{ pageStats.rejected }}</div>
      </div>
    </div>

    <FilterBar>
      <el-select
        v-model="query.status"
        placeholder="状态"
        clearable
        style="width: 150px"
        @change="onSearch"
      >
        <el-option
          v-for="s in statusOptions"
          :key="s.value || 'all'"
          :label="s.label"
          :value="s.value"
        />
      </el-select>
      <el-date-picker
        v-model="query.date"
        type="date"
        value-format="YYYY-MM-DD"
        placeholder="预约覆盖日期"
        style="width: 180px"
        @change="onSearch"
      />
      <el-button size="small" link type="primary" @click="setToday">今日</el-button>
      <template #actions>
        <el-button type="primary" :icon="Search" @click="onSearch">查询</el-button>
        <el-button @click="reset">重置</el-button>
      </template>
    </FilterBar>

    <DataCard>
      <el-table
        :data="rows"
        v-loading="loading"
        stripe
        :header-cell-style="{ background: 'var(--swu-blue-50)', color: 'var(--swu-text)', fontWeight: 600 }"
      >
        <el-table-column type="index" label="#" width="56" />
        <el-table-column label="访客" min-width="190">
          <template #default="{ row }">
            <div class="visitor-name">{{ row.visitor_name }}</div>
            <div class="mono dim">{{ row.id_card }}</div>
          </template>
        </el-table-column>
        <el-table-column label="来访原因" min-width="220">
          <template #default="{ row }">
            <span class="reason">{{ row.visit_reason }}</span>
          </template>
        </el-table-column>
        <el-table-column label="预约时间窗" min-width="260">
          <template #default="{ row }">
            <div class="window-row">
              <span class="mono">{{ row.arrival_date }}</span>
              <span>{{ slotLabel(row.arrival_slot) }}</span>
            </div>
            <div class="window-row">
              <span class="arrow">至</span>
              <span class="mono">{{ row.departure_date }}</span>
              <span>{{ slotLabel(row.departure_slot) }}</span>
              <el-tag v-if="isCrossDay(row)" size="small" type="primary" effect="plain">跨天</el-tag>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)" size="small">
              {{ statusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="审核信息" min-width="180">
          <template #default="{ row }">
            <div class="dim">审核人：{{ row.reviewed_by ?? "—" }}</div>
            <div class="dim">时间：{{ formatTime(row.reviewed_at) }}</div>
            <div v-if="row.reject_reason" class="reject-reason">
              {{ row.reject_reason }}
            </div>
          </template>
        </el-table-column>
        <el-table-column label="提交时间" width="160">
          <template #default="{ row }">
            <span class="mono">{{ formatTime(row.created_at) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="190" fixed="right" align="center">
          <template #default="{ row }">
            <el-button
              v-if="canReview(row)"
              link
              type="success"
              :icon="Check"
              @click="approve(row)"
            >
              通过
            </el-button>
            <el-button
              v-if="canReview(row)"
              link
              type="danger"
              :icon="Close"
              @click="reject(row)"
            >
              拒绝
            </el-button>
            <el-button
              v-if="canCancel(row)"
              link
              type="warning"
              @click="cancel(row)"
            >
              取消
            </el-button>
            <span v-if="!canReview(row) && !canCancel(row)" class="dim">无操作</span>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagi">
        <el-pagination
          background
          :current-page="query.page"
          :page-size="query.page_size"
          :total="total"
          :page-sizes="[20, 50, 100, 200]"
          layout="total, sizes, prev, pager, next, jumper"
          @current-change="onPageChange"
          @size-change="(size: number) => { query.page_size = size; query.page = 1; load(); }"
        />
      </div>
    </DataCard>
  </div>
</template>

<style scoped>
.mini-stats {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 14px;
}

.mini {
  background: var(--swu-bg-elev);
  border: 1px solid var(--swu-border);
  border-radius: 10px;
  padding: 14px 16px;
}

.mini-label {
  font-size: 12px;
  color: var(--swu-text-3);
}

.mini-value {
  margin-top: 4px;
  color: var(--swu-text);
  font-size: 22px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

.text-green { color: var(--swu-success); }
.text-orange { color: var(--swu-warning); }
.text-red { color: var(--swu-danger); }

.visitor-name {
  color: var(--swu-text);
  font-weight: 600;
}

.reason {
  color: var(--swu-text);
  line-height: 1.5;
}

.window-row {
  display: flex;
  align-items: center;
  gap: 8px;
  min-height: 24px;
}

.arrow {
  color: var(--swu-text-3);
  font-size: 12px;
}

.dim {
  color: var(--swu-text-3);
  font-size: 12px;
}

.mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 13px;
}

.reject-reason {
  margin-top: 4px;
  color: var(--swu-danger);
  font-size: 12px;
  line-height: 1.4;
}

.pagi {
  display: flex;
  justify-content: flex-end;
  padding: 14px 4px 2px;
}

@media (max-width: 880px) {
  .mini-stats {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
