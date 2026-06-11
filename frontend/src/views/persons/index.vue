<script setup lang="ts">
/** 人员管理 · 列表 + 筛选 + 分页 + 行操作 + 抽屉编辑。
 *  借鉴 vue-pure-admin/views/list 的工具栏 + table 组合。
 */
import { CirclePlus, Delete, Refresh, Search } from "@element-plus/icons-vue";
import { ElMessage, ElMessageBox } from "element-plus";

import { personsApi, type PersonQuery } from "@/api/persons";
import { systemApi } from "@/api/system";
import type { CollegeOut, FacultyOut, PersonOut } from "@/api/types";
import DataCard from "@/components/common/DataCard.vue";
import FilterBar from "@/components/common/FilterBar.vue";
import PageHeader from "@/components/common/PageHeader.vue";
import PersonEditDrawer from "./components/PersonEditDrawer.vue";

const router = useRouter();

const rows = ref<PersonOut[]>([]);
const total = ref(0);
const loading = ref(false);
const faculties = ref<FacultyOut[]>([]);
const colleges = ref<CollegeOut[]>([]);

const query = reactive<PersonQuery & { faculty_id?: number }>({
  q: "", role: "", status: "", faculty_id: undefined,
  campus: "", dorm_zone: "", page: 1, page_size: 20,
});

const roleOptions = [
  { value: "student", label: "本科生" },
  { value: "graduate", label: "研究生" },
  { value: "teacher", label: "教师" },
  { value: "staff", label: "职工" },
  { value: "visitor", label: "访客" },
];
const statusOptions = [
  { value: "active", label: "正常" },
  { value: "suspended", label: "停用" },
  { value: "graduated", label: "已毕业" },
  { value: "expired", label: "过期" },
];
const campusOptions = [
  { value: "beibei", label: "北碚校区" },
  { value: "rongchang", label: "荣昌校区" },
];
const dormOptions = [
  { value: "nan", label: "楠园" }, { value: "zhu", label: "竹园" },
  { value: "mei", label: "梅园" }, { value: "li", label: "李园" },
  { value: "ju", label: "橘园" }, { value: "tao", label: "桃园" },
  { value: "xing", label: "杏园" },
];

function roleLabel(r: string) { return roleOptions.find((o) => o.value === r)?.label ?? r; }
function statusLabel(s: string) { return statusOptions.find((o) => o.value === s)?.label ?? s; }
function dormLabel(d: string | null) {
  return d ? dormOptions.find((o) => o.value === d)?.label ?? d : "—";
}

async function load() {
  loading.value = true;
  try {
    const params: PersonQuery = { ...query } as PersonQuery;
    (Object.keys(params) as Array<keyof PersonQuery>).forEach((k) => {
      if (params[k] === "" || params[k] === null) delete params[k];
    });
    const r = await personsApi.list(params);
    rows.value = r.items;
    total.value = r.total;
  } finally {
    loading.value = false;
  }
}

async function loadDicts() {
  [faculties.value, colleges.value] = await Promise.all([
    systemApi.faculties(),
    systemApi.colleges(),
  ]);
}

onMounted(async () => {
  await loadDicts();
  await load();
});

function resetQuery() {
  Object.assign(query, {
    q: "", role: "", status: "", faculty_id: undefined,
    campus: "", dorm_zone: "", page: 1,
  });
  load();
}

function onSearch() { query.page = 1; load(); }
function onPageChange(p: number) { query.page = p; load(); }

function viewDetail(row: PersonOut) { router.push(`/persons/${row.id}`); }

async function deletePerson(row: PersonOut) {
  try {
    await ElMessageBox.confirm(
      `确认删除 ${row.name}（${row.external_id}）？该人员的所有人脸样本将一并移除。`,
      "删除人员",
      { type: "warning", confirmButtonText: "删除", cancelButtonText: "取消" },
    );
  } catch { return; }
  await personsApi.remove(row.id);
  ElMessage.success("已删除");
  load();
}

const drawer = ref(false);
const editingId = ref<number | null>(null);
function openCreate() { editingId.value = null; drawer.value = true; }
function openEdit(row: PersonOut) { editingId.value = row.id; drawer.value = true; }
function onDrawerSaved() { drawer.value = false; load(); }

type TagType = "primary" | "success" | "warning" | "info" | "danger";
const roleTagType = (r: string): TagType =>
  (({ student: "primary", graduate: "success", teacher: "warning",
      staff: "info", visitor: "info" } as Record<string, TagType>)[r] || "info");
const statusTagType = (s: string): TagType =>
  (({ active: "success", suspended: "warning", graduated: "info",
      expired: "danger" } as Record<string, TagType>)[s] || "info");
</script>

<template>
  <div>
    <PageHeader title="人员管理" subtitle="本科生 / 研究生 / 教师 / 职工 / 访客">
      <template #actions>
        <el-button :icon="Refresh" circle title="刷新" @click="load" />
        <el-button type="primary" :icon="CirclePlus" @click="openCreate">
          新建人员
        </el-button>
      </template>
    </PageHeader>

    <FilterBar>
      <el-input
        v-model="query.q"
        placeholder="搜索学号 / 姓名 / 学院 / 专业"
        clearable :prefix-icon="Search"
        style="width: 260px" @keyup.enter="onSearch"
      />
      <el-select v-model="query.faculty_id" placeholder="学部" clearable @change="onSearch">
        <el-option v-for="f in faculties" :key="f.id" :label="f.name" :value="f.id" />
      </el-select>
      <el-select v-model="query.role" placeholder="身份" clearable @change="onSearch">
        <el-option v-for="o in roleOptions" :key="o.value" :label="o.label" :value="o.value" />
      </el-select>
      <el-select v-model="query.status" placeholder="状态" clearable @change="onSearch">
        <el-option v-for="o in statusOptions" :key="o.value" :label="o.label" :value="o.value" />
      </el-select>
      <el-select v-model="query.campus" placeholder="校区" clearable @change="onSearch">
        <el-option v-for="o in campusOptions" :key="o.value" :label="o.label" :value="o.value" />
      </el-select>
      <el-select v-model="query.dorm_zone" placeholder="园区" clearable @change="onSearch">
        <el-option v-for="o in dormOptions" :key="o.value" :label="o.label" :value="o.value" />
      </el-select>

      <template #actions>
        <el-button type="primary" :icon="Search" @click="onSearch">搜索</el-button>
        <el-button @click="resetQuery">重置</el-button>
      </template>
    </FilterBar>

    <DataCard>
      <el-table
        :data="rows" v-loading="loading" stripe
        :row-style="{ height: '52px' }"
        :header-cell-style="{ background: 'var(--swu-blue-50)', color: 'var(--swu-text)', fontWeight: 600 }"
        @row-click="viewDetail"
      >
        <el-table-column type="index" label="#" width="56" />
        <el-table-column prop="external_id" label="学号 / 工号" width="170">
          <template #default="{ row }"><span class="mono">{{ row.external_id }}</span></template>
        </el-table-column>
        <el-table-column prop="name" label="姓名" width="120">
          <template #default="{ row }">
            <div class="cell-name">
              <span class="avatar">{{ row.name.slice(0, 1) }}</span>
              <span>{{ row.name }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="role" label="身份" width="90">
          <template #default="{ row }">
            <el-tag :type="roleTagType(row.role)" size="small" effect="light">
              {{ roleLabel(row.role) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="学部 · 学院" min-width="240">
          <template #default="{ row }">
            <div class="cell-dim">{{ row.faculty_name || "—" }}</div>
            <div>{{ row.school_name || "—" }}</div>
          </template>
        </el-table-column>
        <el-table-column prop="major" label="专业" min-width="140" />
        <el-table-column prop="class_code" label="班级" width="120" />
        <el-table-column prop="dorm_zone" label="园区" width="76">
          <template #default="{ row }"><span>{{ dormLabel(row.dorm_zone) }}</span></template>
        </el-table-column>
        <el-table-column prop="embedding_count" label="样本" width="78" align="center">
          <template #default="{ row }">
            <el-tag size="small" effect="plain"
              :type="row.embedding_count > 0 ? 'success' : 'info'">
              {{ row.embedding_count }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="88">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)" size="small">
              {{ statusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="170" fixed="right" align="center">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click.stop="viewDetail(row)">详情</el-button>
            <el-button link type="primary" size="small" @click.stop="openEdit(row)">编辑</el-button>
            <el-button link type="danger"  size="small" :icon="Delete"
              @click.stop="deletePerson(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagi">
        <el-pagination
          background
          :current-page="query.page" :page-size="query.page_size" :total="total"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next, jumper"
          @current-change="onPageChange"
          @size-change="(s: number) => { query.page_size = s; query.page = 1; load(); }"
        />
      </div>
    </DataCard>

    <PersonEditDrawer
      v-model:open="drawer"
      :id="editingId"
      :faculties="faculties"
      :colleges="colleges"
      @saved="onDrawerSaved"
    />
  </div>
</template>

<style scoped>
.mono { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 13px; }
.cell-name { display: flex; align-items: center; gap: 10px; }
.avatar {
  display: inline-flex; align-items: center; justify-content: center;
  width: 28px; height: 28px;
  background: linear-gradient(135deg, #003D7A, #1565C0);
  color: #fff; border-radius: 50%;
  font-size: 12px; font-weight: 600;
}
.cell-dim { font-size: 11px; color: var(--swu-text-3); line-height: 1.4; }
.pagi { display: flex; justify-content: flex-end; padding: 14px 4px 2px; }
:deep(.el-table) { --el-table-row-hover-bg-color: var(--swu-blue-50); cursor: pointer; }
</style>
