<script setup lang="ts">
/** 人员详情：信息卡 + 嵌入网格 + 通行历史。 */
import { ArrowLeft, Camera, Delete, Edit } from "@element-plus/icons-vue";
import { ElMessage, ElMessageBox } from "element-plus";

import { logsApi } from "@/api/access-logs";
import { personsApi } from "@/api/persons";
import { systemApi } from "@/api/system";
import type { AccessLogOut, CollegeOut, FacultyOut, PersonOut } from "@/api/types";
import DataCard from "@/components/common/DataCard.vue";
import PageHeader from "@/components/common/PageHeader.vue";
import PersonEditDrawer from "./components/PersonEditDrawer.vue";

const route = useRoute();
const router = useRouter();
const personId = computed(() => Number(route.params.id));

const person = ref<PersonOut | null>(null);
const faces = ref<Array<{
  id: number;
  sha256: string;
  image_path: string | null;
  model_name: string;
  created_at: string;
}>>([]);
const logs = ref<AccessLogOut[]>([]);
const loading = ref(false);

const faculties = ref<FacultyOut[]>([]);
const colleges = ref<CollegeOut[]>([]);

async function load() {
  loading.value = true;
  try {
    const [p, ff, cc] = await Promise.all([
      personsApi.get(personId.value),
      systemApi.faculties(),
      systemApi.colleges(),
    ]);
    person.value = p;
    faculties.value = ff;
    colleges.value = cc;

    const [fs, ls] = await Promise.all([
      personsApi.listFaces(personId.value),
      logsApi.list({ person_id: personId.value, page: 1, page_size: 30 }),
    ]);
    faces.value = fs as typeof faces.value;
    logs.value = ls.items;
  } finally {
    loading.value = false;
  }
}
onMounted(load);

const roleLabel: Record<string, string> = {
  student: "本科生", graduate: "研究生", teacher: "教师", staff: "职工", visitor: "访客",
};
const statusLabel: Record<string, string> = {
  active: "正常", suspended: "停用", graduated: "已毕业", expired: "过期",
};
const dormLabel: Record<string, string> = {
  nan: "楠园", zhu: "竹园", mei: "梅园", li: "李园", ju: "橘园", tao: "桃园", xing: "杏园",
};
const statusTagType: Record<string, string> = {
  active: "success", suspended: "warning", graduated: "info", expired: "danger",
};
const decisionTagType: Record<string, string> = {
  granted: "success", rejected: "danger", spoof: "warning", no_face: "info",
};
const decisionLabel: Record<string, string> = {
  granted: "通行", rejected: "未识别", spoof: "活体拒", no_face: "无脸",
};

const drawer = ref(false);

async function deleteFace(face: typeof faces.value[number]) {
  try {
    await ElMessageBox.confirm(
      "确认删除此张人脸样本？同步从向量库移除。", "删除",
      { type: "warning", confirmButtonText: "删除", cancelButtonText: "取消" },
    );
  } catch { return; }
  try {
    const token = localStorage.getItem("swu_face_token");
    const r = await fetch(`/api/persons/${personId.value}/faces/${face.id}`, {
      method: "DELETE",
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!r.ok) throw new Error(`${r.status}`);
    ElMessage.success("已删除");
    load();
  } catch {
    ElMessage.error("删除失败");
  }
}

function goCapture() {
  if (!person.value) return;
  router.push({ path: "/persons/capture", query: { id: String(person.value.id) } });
}
</script>

<template>
  <div v-loading="loading">
    <PageHeader
      :title="person ? person.name : '加载中...'"
      :subtitle="person?.external_id"
    >
      <template #actions>
        <el-button :icon="ArrowLeft" @click="router.back()">返回</el-button>
        <el-button :icon="Camera" type="primary" plain @click="goCapture">采集人脸</el-button>
        <el-button :icon="Edit" type="primary" @click="drawer = true">编辑</el-button>
      </template>
    </PageHeader>

    <div v-if="person" class="grid">
      <DataCard class="info-card">
        <template #header>
          <span class="head">基本信息</span>
          <el-tag :type="(statusTagType[person.status] as any)" size="small">
            {{ statusLabel[person.status] }}
          </el-tag>
        </template>

        <div class="hero">
          <div class="avatar-big">{{ person.name.slice(0, 1) }}</div>
          <div>
            <div class="name">{{ person.name }}</div>
            <div class="sub">
              <el-tag size="small" effect="light">{{ roleLabel[person.role] }}</el-tag>
              <span class="mono">{{ person.external_id }}</span>
            </div>
          </div>
        </div>

        <el-descriptions :column="1" border size="default" class="desc">
          <el-descriptions-item label="学部">{{ person.faculty_name || "—" }}</el-descriptions-item>
          <el-descriptions-item label="学院">{{ person.school_name || "—" }}</el-descriptions-item>
          <el-descriptions-item label="专业">{{ person.major || "—" }}</el-descriptions-item>
          <el-descriptions-item label="班级">{{ person.class_code || "—" }}</el-descriptions-item>
          <el-descriptions-item label="入学年">{{ person.enrollment_year || "—" }}</el-descriptions-item>
          <el-descriptions-item label="校区">
            {{ person.campus === "beibei" ? "北碚校区" : "荣昌校区" }}
          </el-descriptions-item>
          <el-descriptions-item label="园区">
            {{ person.dorm_zone ? dormLabel[person.dorm_zone] : "—" }}
          </el-descriptions-item>
          <el-descriptions-item label="手机">{{ person.phone || "—" }}</el-descriptions-item>
          <el-descriptions-item label="邮箱">{{ person.email || "—" }}</el-descriptions-item>
          <el-descriptions-item label="备注">{{ person.note || "—" }}</el-descriptions-item>
          <el-descriptions-item label="人脸样本">
            <el-tag size="small" :type="person.embedding_count > 0 ? 'success' : 'info'">
              {{ person.embedding_count }} 张
            </el-tag>
          </el-descriptions-item>
        </el-descriptions>
      </DataCard>

      <div class="right">
        <DataCard>
          <template #header>
            <span class="head">已注册人脸样本</span>
            <span class="dim">{{ faces.length }} 张 · 向量库 (FAISS)</span>
          </template>
          <div v-if="faces.length === 0" class="empty">
            <el-empty description="尚无人脸样本，点击右上「采集人脸」添加" />
          </div>
          <div v-else class="faces-grid">
            <div v-for="f in faces" :key="f.id" class="face-card">
              <div class="face-thumb">
                <el-icon :size="32"><Camera /></el-icon>
              </div>
              <div class="face-meta">
                <div class="face-id">#{{ f.id }}</div>
                <div class="dim mono">{{ f.sha256.slice(0, 12) }}…</div>
                <div class="dim">{{ f.created_at.replace("T", " ").slice(0, 16) }}</div>
                <div class="dim">{{ f.model_name }}</div>
              </div>
              <el-button
                :icon="Delete" link type="danger" size="small"
                class="face-del" @click="deleteFace(f)"
              />
            </div>
          </div>
        </DataCard>

        <DataCard>
          <template #header>
            <span class="head">最近通行</span>
            <span class="dim">最多 30 条</span>
          </template>
          <el-table :data="logs" size="small" :show-header="true">
            <el-table-column label="时间" width="160">
              <template #default="{ row }">
                {{ row.ts.replace('T',' ').slice(0,19) }}
              </template>
            </el-table-column>
            <el-table-column prop="gate_name" label="门禁" min-width="160" />
            <el-table-column label="决策" width="100">
              <template #default="{ row }">
                <el-tag :type="(decisionTagType[row.decision] as any)" size="small">
                  {{ decisionLabel[row.decision] || row.decision }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="相似度" width="100">
              <template #default="{ row }">
                {{ row.score == null ? "—" : row.score.toFixed(3) }}
              </template>
            </el-table-column>
            <el-table-column label="活体分" width="100">
              <template #default="{ row }">
                {{ row.spoof_score == null ? "—" : row.spoof_score.toFixed(3) }}
              </template>
            </el-table-column>
          </el-table>
        </DataCard>
      </div>
    </div>

    <PersonEditDrawer
      v-if="person"
      v-model:open="drawer"
      :id="person.id"
      :faculties="faculties"
      :colleges="colleges"
      @saved="() => { drawer = false; load(); }"
    />
  </div>
</template>

<style scoped>
.grid {
  display: grid;
  grid-template-columns: 360px 1fr;
  gap: 14px;
}
@media (max-width: 1024px) {
  .grid { grid-template-columns: 1fr; }
}
.right { display: flex; flex-direction: column; gap: 14px; }

.head { font-weight: 600; }
.dim { font-size: 12px; color: var(--swu-text-3); }

.hero { display: flex; align-items: center; gap: 14px; margin-bottom: 14px; }
.avatar-big {
  width: 64px; height: 64px;
  background: linear-gradient(135deg, #003D7A, #1565C0);
  color: #fff; border-radius: 50%;
  display: inline-flex; align-items: center; justify-content: center;
  font-size: 28px; font-weight: 600;
  box-shadow: 0 4px 12px rgba(0, 61, 122, 0.32);
}
.name { font-size: 20px; font-weight: 600; }
.sub { display: flex; gap: 10px; align-items: center; margin-top: 4px; }
.mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  color: var(--swu-text-3); font-size: 13px;
}

.desc :deep(.el-descriptions__label) { width: 84px; }

.faces-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 12px;
}
.face-card {
  position: relative;
  border: 1px solid var(--swu-border);
  border-radius: 10px;
  padding: 12px;
  display: flex; gap: 10px; align-items: flex-start;
  transition: all 0.15s ease;
}
.face-card:hover {
  border-color: var(--swu-blue);
  box-shadow: 0 4px 12px rgba(0, 61, 122, 0.08);
}
.face-thumb {
  width: 48px; height: 48px;
  background: var(--swu-blue-50);
  color: var(--swu-blue);
  border-radius: 8px;
  display: inline-flex; align-items: center; justify-content: center;
  flex-shrink: 0;
}
.face-meta { flex: 1; min-width: 0; }
.face-id { font-size: 13px; font-weight: 600; color: var(--swu-text); }
.face-del { position: absolute; top: 8px; right: 8px; }
.empty { padding: 40px 0; }
</style>
