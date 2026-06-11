<script setup lang="ts">
/** 门禁管理 · 卡片网格 + 状态切换。 */
import { CirclePlus, Connection, MapLocation, Refresh } from "@element-plus/icons-vue";
import { ElMessage, type FormInstance, type FormRules } from "element-plus";

import { gatesApi } from "@/api/gates";
import type { GateOut } from "@/api/types";
import DataCard from "@/components/common/DataCard.vue";
import PageHeader from "@/components/common/PageHeader.vue";

const rows = ref<GateOut[]>([]);
const loading = ref(false);
const createOpen = ref(false);
const creating = ref(false);
const createFormRef = ref<FormInstance>();

type GateCampus = GateOut["campus"];
type GateDirection = GateOut["direction"];
type GateStatus = GateOut["status"];

const createForm = reactive({
  code: "",
  name: "",
  campus: "beibei" as GateCampus,
  location: "",
  direction: "both" as GateDirection,
  ip_address: "",
  status: "offline" as GateStatus,
  note: "",
});

const createRules: FormRules = {
  code: [
    { required: true, message: "请输入门禁编码", trigger: "blur" },
    { max: 32, message: "门禁编码最多 32 个字符", trigger: "blur" },
  ],
  name: [
    { required: true, message: "请输入门禁名称", trigger: "blur" },
    { max: 128, message: "门禁名称最多 128 个字符", trigger: "blur" },
  ],
  campus: [{ required: true, message: "请选择校区", trigger: "change" }],
  direction: [{ required: true, message: "请选择通行方向", trigger: "change" }],
  status: [{ required: true, message: "请选择初始状态", trigger: "change" }],
};

async function load() {
  loading.value = true;
  try { rows.value = await gatesApi.list(); }
  finally { loading.value = false; }
}
onMounted(load);

const grouped = computed(() => {
  const out: Record<string, GateOut[]> = { beibei: [], rongchang: [] };
  for (const g of rows.value) {
    (out[g.campus] ||= []).push(g);
  }
  return out;
});

const stats = computed(() => ({
  total: rows.value.length,
  online: rows.value.filter((g) => g.status === "online").length,
  offline: rows.value.filter((g) => g.status === "offline").length,
  disabled: rows.value.filter((g) => g.status === "disabled").length,
}));

const statusOrder = ["online", "offline", "disabled"] as const;
function statusLabel(s: string) {
  return ({ online: "在线", offline: "离线", disabled: "停用" } as Record<string, string>)[s] || s;
}

async function setStatus(g: GateOut, status: GateOut["status"]) {
  if (g.status === status) return;
  await gatesApi.setStatus(g.id, status);
  ElMessage.success(`${g.name} 已设为 ${statusLabel(status)}`);
  load();
}

function dirLabel(d: string) {
  return ({ in: "仅入", out: "仅出", both: "双向" } as Record<string, string>)[d] || d;
}

function resetCreateForm() {
  Object.assign(createForm, {
    code: "",
    name: "",
    campus: "beibei",
    location: "",
    direction: "both",
    ip_address: "",
    status: "offline",
    note: "",
  });
  createFormRef.value?.clearValidate();
}

function openCreateDialog() {
  resetCreateForm();
  createOpen.value = true;
}

function blankToNull(value: string) {
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
}

async function createGate() {
  if (!createFormRef.value) return;
  await createFormRef.value.validate();
  creating.value = true;
  try {
    const created = await gatesApi.create({
      code: createForm.code.trim(),
      name: createForm.name.trim(),
      campus: createForm.campus,
      location: blankToNull(createForm.location),
      direction: createForm.direction,
      ip_address: blankToNull(createForm.ip_address),
      status: createForm.status,
      note: blankToNull(createForm.note),
    });
    ElMessage.success(`已创建门禁：${created.name}`);
    createOpen.value = false;
    await load();
  } finally {
    creating.value = false;
  }
}
</script>

<template>
  <div>
    <PageHeader title="门禁管理" subtitle="按校区组织 · 在线/离线/停用三态">
      <template #actions>
        <el-button :icon="Refresh" circle title="刷新" @click="load" />
        <el-button type="primary" :icon="CirclePlus" @click="openCreateDialog">
          新建门禁
        </el-button>
      </template>
    </PageHeader>

    <div class="mini-stats">
      <div class="mini">
        <div class="mini-label">总门禁</div>
        <div class="mini-value">{{ stats.total }}</div>
      </div>
      <div class="mini">
        <div class="mini-label">在线</div>
        <div class="mini-value text-green">{{ stats.online }}</div>
      </div>
      <div class="mini">
        <div class="mini-label">离线</div>
        <div class="mini-value text-orange">{{ stats.offline }}</div>
      </div>
      <div class="mini">
        <div class="mini-label">停用</div>
        <div class="mini-value text-red">{{ stats.disabled }}</div>
      </div>
    </div>

    <template v-for="campusKey in ['beibei', 'rongchang']" :key="campusKey">
      <DataCard v-if="grouped[campusKey]?.length">
        <template #header>
          <div class="campus-head">
            <el-icon><MapLocation /></el-icon>
            <span class="head">{{ campusKey === "beibei" ? "北碚校区" : "荣昌校区" }}</span>
            <span class="dim">{{ grouped[campusKey].length }} 个门禁</span>
          </div>
        </template>
        <div class="grid">
          <div
            v-for="g in grouped[campusKey]"
            :key="g.id"
            :class="['gate-card', `is-${g.status}`]"
          >
            <div class="card-top">
              <div class="status-orb">
                <span class="orb-inner" />
              </div>
              <div class="meta">
                <div class="name">{{ g.name }}</div>
                <div class="dim mono">{{ g.code }}</div>
              </div>
            </div>
            <div class="loc">
              <el-icon><Connection /></el-icon>
              {{ g.location || "—" }}
            </div>
            <div class="badge-row">
              <el-tag size="small" effect="plain">{{ dirLabel(g.direction) }}</el-tag>
              <el-tag size="small" effect="plain" v-if="g.ip_address">IP {{ g.ip_address }}</el-tag>
            </div>
            <div class="card-foot">
              <el-radio-group
                :model-value="g.status" size="small"
                @change="(s) => s && setStatus(g, String(s) as GateOut['status'])"
              >
                <el-radio-button v-for="s in statusOrder" :key="s" :value="s">
                  {{ statusLabel(s) }}
                </el-radio-button>
              </el-radio-group>
            </div>
          </div>
        </div>
      </DataCard>
    </template>

    <div v-if="!loading && rows.length === 0" style="padding: 60px 0;">
      <el-empty description="尚无门禁数据" />
    </div>

    <el-dialog
      v-model="createOpen"
      title="新建门禁"
      width="560px"
      destroy-on-close
      align-center
      @closed="resetCreateForm"
    >
      <el-form
        ref="createFormRef"
        :model="createForm"
        :rules="createRules"
        label-width="96px"
      >
        <el-form-item label="门禁编码" prop="code">
          <el-input
            v-model="createForm.code"
            maxlength="32"
            placeholder="如：GATE-09 或 BEIBEI-NORTH-09"
            show-word-limit
          />
        </el-form-item>
        <el-form-item label="门禁名称" prop="name">
          <el-input
            v-model="createForm.name"
            maxlength="128"
            placeholder="如：新建门（9号门）"
            show-word-limit
          />
        </el-form-item>
        <el-form-item label="校区" prop="campus">
          <el-radio-group v-model="createForm.campus">
            <el-radio-button value="beibei">北碚校区</el-radio-button>
            <el-radio-button value="rongchang">荣昌校区</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="位置">
          <el-input
            v-model="createForm.location"
            maxlength="255"
            placeholder="如：北碚校区北区入口"
          />
        </el-form-item>
        <el-form-item label="通行方向" prop="direction">
          <el-radio-group v-model="createForm.direction">
            <el-radio-button value="in">仅入</el-radio-button>
            <el-radio-button value="out">仅出</el-radio-button>
            <el-radio-button value="both">双向</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="初始状态" prop="status">
          <el-radio-group v-model="createForm.status">
            <el-radio-button value="online">在线</el-radio-button>
            <el-radio-button value="offline">离线</el-radio-button>
            <el-radio-button value="disabled">停用</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="IP 地址">
          <el-input
            v-model="createForm.ip_address"
            maxlength="64"
            placeholder="可选，如：192.168.1.20"
          />
        </el-form-item>
        <el-form-item label="备注">
          <el-input
            v-model="createForm.note"
            type="textarea"
            :rows="3"
            placeholder="可选"
          />
        </el-form-item>
      </el-form>

      <template #footer>
        <div class="dialog-footer">
          <el-button @click="createOpen = false">取消</el-button>
          <el-button type="primary" :loading="creating" @click="createGate">创建</el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.head { font-weight: 600; }
.dim { font-size: 12px; color: var(--swu-text-3); }
.mono { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }

.mini-stats {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 14px;
}
.mini {
  background: var(--swu-bg-elev);
  border: 1px solid var(--swu-border);
  border-radius: 10px;
  padding: 14px 16px;
}
.mini-label { font-size: 12px; color: var(--swu-text-3); }
.mini-value { margin-top: 4px; font-size: 22px; font-weight: 600; font-variant-numeric: tabular-nums; }
.text-green  { color: var(--swu-success); }
.text-orange { color: var(--swu-warning); }
.text-red    { color: var(--swu-danger); }

.campus-head { display: flex; align-items: center; gap: 10px; }

.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 14px;
}

.gate-card {
  position: relative;
  background: linear-gradient(135deg, rgba(0,61,122,0.02), rgba(0,61,122,0.06));
  border: 1px solid var(--swu-border);
  border-radius: 12px;
  padding: 16px 18px;
  transition: all 0.18s ease;
  overflow: hidden;
}
.gate-card::before {
  content: "";
  position: absolute; top: -50px; right: -50px;
  width: 120px; height: 120px; border-radius: 50%;
  opacity: 0.18; filter: blur(36px);
}
.gate-card.is-online::before   { background: #52C41A; }
.gate-card.is-offline::before  { background: #FAAD14; }
.gate-card.is-disabled::before { background: #8C8C8C; }

.gate-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 24px rgba(0, 61, 122, 0.10);
  border-color: var(--swu-blue-light);
}

.card-top { display: flex; gap: 12px; align-items: flex-start; }
.status-orb {
  width: 32px; height: 32px; border-radius: 50%;
  display: inline-flex; align-items: center; justify-content: center;
  background: rgba(0,0,0,0.04);
}
.orb-inner {
  width: 10px; height: 10px; border-radius: 50%;
  background: #8C8C8C;
}
.is-online .orb-inner {
  background: #52C41A;
  box-shadow: 0 0 0 4px rgba(82,196,26,0.18), 0 0 10px #52C41A;
  animation: pulse 1.6s ease-in-out infinite;
}
.is-offline  .orb-inner { background: #FAAD14; }
.is-disabled .orb-inner { background: #8C8C8C; opacity: 0.6; }

@keyframes pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50%      { opacity: 0.55; transform: scale(0.7); }
}

.meta .name { font-size: 15px; font-weight: 600; color: var(--swu-text); }

.loc {
  margin-top: 12px;
  font-size: 12px; color: var(--swu-text-2);
  display: flex; align-items: center; gap: 6px;
  line-height: 1.5;
}
.badge-row { margin-top: 10px; display: flex; gap: 6px; flex-wrap: wrap; }
.card-foot { margin-top: 14px; }
</style>
