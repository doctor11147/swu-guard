<script setup lang="ts">
import { ArrowLeft, Calendar, Camera, Check, Search, Upload, User, VideoCamera, VideoPause } from "@element-plus/icons-vue";
import { ElMessage } from "element-plus";

import {
  visitorsApi,
  type AppointmentOut,
  type VisitorFaceRegisterOut,
} from "@/api/visitors";
import { CameraUnavailableError, closeCamera, openCamera } from "@/utils/camera";

const router = useRouter();

const slotOptions = [
  { value: 0, label: "00:00-04:00" },
  { value: 1, label: "04:00-08:00" },
  { value: 2, label: "08:00-12:00" },
  { value: 3, label: "12:00-16:00" },
  { value: 4, label: "16:00-20:00" },
  { value: 5, label: "20:00-24:00" },
];

const registerForm = reactive({
  name: "",
  id_card: "",
  phone: "",
  email: "",
  note: "",
});
const appointmentForm = reactive({
  id_card: "",
  visit_reason: "",
  arrival_date: new Date().toISOString().slice(0, 10),
  departure_date: new Date().toISOString().slice(0, 10),
  arrival_slot: 2,
  departure_slot: 3,
});
const lookupIdCard = ref("");
const faceFiles = ref<File[]>([]);
const faceVideoRef = ref<HTMLVideoElement>();
const captureCanvas = document.createElement("canvas");
const DEFAULT_CAPTURE_COUNT = 5;
const DEFAULT_CAPTURE_INTERVAL_MS = 350;
const stream = ref<MediaStream | null>(null);
const cameraOn = computed(() => !!stream.value);
const capturing = ref(false);

const registering = ref(false);
const uploadingFaces = ref(false);
const submittingAppointment = ref(false);
const lookingUp = ref(false);
const faceResult = ref<VisitorFaceRegisterOut | null>(null);
const appointments = ref<AppointmentOut[]>([]);
const previews = ref<Array<{ blob: Blob; url: string; selected: boolean }>>([]);

function syncIdCard(value: string) {
  appointmentForm.id_card = value;
  lookupIdCard.value = value;
}

const currentIdCard = computed(() => (
  appointmentForm.id_card || registerForm.id_card || lookupIdCard.value
).trim().toUpperCase());

async function submitRegister() {
  if (!registerForm.name || !registerForm.id_card) {
    ElMessage.warning("请填写姓名和身份证号");
    return;
  }
  registering.value = true;
  try {
    const out = await visitorsApi.register({
      id_card: registerForm.id_card,
      name: registerForm.name,
      phone: registerForm.phone || undefined,
      email: registerForm.email || undefined,
      note: registerForm.note || undefined,
    });
    syncIdCard(out.id_card);
    ElMessage.success(out.created ? "访客身份已创建" : "访客身份已更新");
  } finally {
    registering.value = false;
  }
}

function onFaceChange(file: { raw?: File }) {
  if (!file.raw) return;
  faceFiles.value.push(file.raw);
  const url = URL.createObjectURL(file.raw);
  previews.value.push({ blob: file.raw, url, selected: true });
}

function clearFaces() {
  faceFiles.value = [];
  previews.value.forEach((p) => URL.revokeObjectURL(p.url));
  previews.value = [];
  faceResult.value = null;
}

async function startCamera() {
  try {
    stream.value = await openCamera();
    if (faceVideoRef.value) {
      faceVideoRef.value.srcObject = stream.value;
      await faceVideoRef.value.play();
    }
  } catch (e: unknown) {
    const msg = e instanceof CameraUnavailableError
      ? e.message
      : e instanceof Error ? e.message : String(e);
    ElMessage({ type: "error", message: msg, duration: 6000, showClose: true });
  }
}

function stopCamera() {
  closeCamera(stream.value);
  stream.value = null;
}

async function captureFrames() {
  if (!faceVideoRef.value || !cameraOn.value) {
    ElMessage.warning("请先打开摄像头");
    return;
  }
  capturing.value = true;
  faceResult.value = null;

  const v = faceVideoRef.value;
  captureCanvas.width = v.videoWidth || 640;
  captureCanvas.height = v.videoHeight || 480;
  const ctx = captureCanvas.getContext("2d");
  if (!ctx) { capturing.value = false; return; }

  for (let i = 0; i < DEFAULT_CAPTURE_COUNT; i++) {
    ctx.drawImage(v, 0, 0);
    const blob: Blob = await new Promise((resolve) =>
      captureCanvas.toBlob((b) => resolve(b!), "image/jpeg", 0.92),
    );
    const url = URL.createObjectURL(blob);
    previews.value.push({ blob, url, selected: true });
    if (i < DEFAULT_CAPTURE_COUNT - 1) {
      await new Promise((r) => setTimeout(r, DEFAULT_CAPTURE_INTERVAL_MS));
    }
  }
  capturing.value = false;
  ElMessage.success(`已抓取 ${DEFAULT_CAPTURE_COUNT} 帧`);
}

function toggleFrame(index: number) {
  previews.value[index].selected = !previews.value[index].selected;
}

function removeFrame(index: number) {
  URL.revokeObjectURL(previews.value[index].url);
  previews.value.splice(index, 1);
}

async function submitFaces() {
  const idCard = currentIdCard.value;
  if (!idCard) {
    ElMessage.warning("请先填写身份证号");
    return;
  }
  const selected = previews.value.filter((p) => p.selected);
  if (selected.length === 0) {
    ElMessage.warning("请至少勾选一张人脸样本");
    return;
  }
  uploadingFaces.value = true;
  try {
    const files = selected.map(
      (p, i) => new File([p.blob], `visitor_${Date.now()}_${i}.jpg`, { type: "image/jpeg" }),
    );
    const result = await visitorsApi.registerFaces(idCard, files);
    faceResult.value = result;
    if (result.added === 0 && result.skipped_duplicates > 0) {
      ElMessage.warning(`未新增样本：检测到 ${result.skipped_duplicates} 张重复照片`);
    } else {
      ElMessage.success(`已入库 ${result.added} 张人脸样本`);
    }
  } finally {
    uploadingFaces.value = false;
  }
}

async function submitAppointment() {
  if (
    !appointmentForm.id_card ||
    !appointmentForm.visit_reason ||
    !appointmentForm.arrival_date ||
    !appointmentForm.departure_date
  ) {
    ElMessage.warning("请完整填写预约信息");
    return;
  }
  const start = `${appointmentForm.arrival_date}-${appointmentForm.arrival_slot}`;
  const end = `${appointmentForm.departure_date}-${appointmentForm.departure_slot}`;
  if (end < start) {
    ElMessage.warning("离开时间不得早于到达时间");
    return;
  }
  submittingAppointment.value = true;
  try {
    await visitorsApi.createAppointment({ ...appointmentForm });
    lookupIdCard.value = appointmentForm.id_card;
    ElMessage.success("预约已提交，等待门卫审批");
    await lookupAppointments();
  } finally {
    submittingAppointment.value = false;
  }
}

async function lookupAppointments() {
  if (!lookupIdCard.value) {
    ElMessage.warning("请填写身份证号");
    return;
  }
  lookingUp.value = true;
  try {
    const page = await visitorsApi.lookup(lookupIdCard.value);
    appointments.value = page.items;
  } finally {
    lookingUp.value = false;
  }
}

function statusText(status: AppointmentOut["status"]) {
  return ({
    pending: "待审批",
    approved: "已通过",
    rejected: "已拒绝",
    expired: "已过期",
    cancelled: "已取消",
  } as const)[status];
}

function statusType(status: AppointmentOut["status"]) {
  return ({
    pending: "warning",
    approved: "success",
    rejected: "danger",
    expired: "info",
    cancelled: "info",
  } as const)[status];
}

onBeforeUnmount(() => {
  stopCamera();
  previews.value.forEach((p) => URL.revokeObjectURL(p.url));
});
</script>

<template>
  <main class="visitor-page">
    <div class="visitor-shell">
      <header class="visitor-head">
        <button type="button" class="back" @click="router.push('/')">
          <el-icon><ArrowLeft /></el-icon>
          <span>返回首页</span>
        </button>
        <div>
          <h1>访客通道</h1>
          <p>注册访客身份、录入人脸样本并提交入校预约。</p>
        </div>
      </header>

      <section class="grid">
        <article class="panel">
          <div class="panel-head">
            <span class="icon blue"><el-icon><User /></el-icon></span>
            <div>
              <h2>身份登记</h2>
              <p>身份证号作为访客唯一标识。</p>
            </div>
          </div>
          <el-form label-position="top">
            <el-form-item label="姓名">
              <el-input v-model="registerForm.name" placeholder="请输入访客姓名" />
            </el-form-item>
            <el-form-item label="身份证号">
              <el-input
                v-model="registerForm.id_card"
                maxlength="18"
                placeholder="18 位身份证号"
                @change="syncIdCard"
              />
            </el-form-item>
            <el-form-item label="手机号">
              <el-input v-model="registerForm.phone" placeholder="可选" />
            </el-form-item>
            <el-form-item label="备注">
              <el-input v-model="registerForm.note" type="textarea" :rows="2" placeholder="可选" />
            </el-form-item>
            <el-button type="primary" :loading="registering" @click="submitRegister">
              保存身份
            </el-button>
          </el-form>
        </article>

        <article class="panel">
          <div class="panel-head">
            <span class="icon gold"><el-icon><Camera /></el-icon></span>
            <div>
              <h2>人脸样本</h2>
              <p>请使用现场摄像头采集，或上传近期清晰照片。</p>
            </div>
          </div>
          <div class="camera-box" :class="!cameraOn && 'is-off'">
            <video ref="faceVideoRef" muted playsinline />
            <div v-if="!cameraOn" class="camera-mask">
              <el-icon :size="42"><VideoPause /></el-icon>
              <p>摄像头未开启</p>
            </div>
          </div>
          <div class="actions">
            <el-button v-if="!cameraOn" :icon="VideoCamera" @click="startCamera">
              开启摄像头
            </el-button>
            <el-button v-else :icon="VideoPause" @click="stopCamera">关闭摄像头</el-button>
            <el-button
              type="primary"
              :icon="Camera"
              :loading="capturing"
              :disabled="!cameraOn"
              @click="captureFrames"
            >
              从摄像头抓取
            </el-button>
          </div>
          <div v-if="previews.length" class="frames">
            <div
              v-for="(p, i) in previews"
              :key="i"
              :class="['frame', p.selected && 'is-selected']"
              @click="toggleFrame(i)"
            >
              <img :src="p.url" alt="" />
              <span class="frame-check">
                <el-icon v-if="p.selected" :size="14"><Check /></el-icon>
              </span>
              <button type="button" class="frame-del" @click.stop="removeFrame(i)">×</button>
            </div>
          </div>
          <div v-else class="empty">暂无候选帧，请先从摄像头抓取。</div>
          <el-upload
            class="upload-fallback"
            multiple
            accept="image/*"
            :auto-upload="false"
            :show-file-list="false"
            :on-change="onFaceChange"
          >
            <el-button text :icon="Upload">上传照片</el-button>
          </el-upload>
          <div class="actions">
            <el-button @click="clearFaces">清空</el-button>
            <el-button type="primary" :loading="uploadingFaces" @click="submitFaces">
              入库 · {{ previews.filter((p) => p.selected).length }} 张
            </el-button>
          </div>
          <p v-if="faceResult" class="result-line">
            入库 {{ faceResult.added }}，重复 {{ faceResult.skipped_duplicates }}，
            无脸 {{ faceResult.skipped_no_face }}，
            活体拒 {{ faceResult.skipped_spoof }}，质量拒 {{ faceResult.skipped_quality }}
          </p>
        </article>

        <article class="panel">
          <div class="panel-head">
            <span class="icon red"><el-icon><Calendar /></el-icon></span>
            <div>
              <h2>提交预约</h2>
              <p>预约通过后，访客刷脸才可通行。</p>
            </div>
          </div>
          <el-form label-position="top">
            <el-form-item label="身份证号">
              <el-input v-model="appointmentForm.id_card" maxlength="18" placeholder="18 位身份证号" />
            </el-form-item>
            <div class="slot-row">
              <el-form-item label="到达日期">
                <el-date-picker
                  v-model="appointmentForm.arrival_date"
                  type="date"
                  value-format="YYYY-MM-DD"
                  placeholder="选择到达日期"
                  class="full-input"
                />
              </el-form-item>
              <el-form-item label="离开日期">
                <el-date-picker
                  v-model="appointmentForm.departure_date"
                  type="date"
                  value-format="YYYY-MM-DD"
                  placeholder="选择离开日期"
                  class="full-input"
                />
              </el-form-item>
            </div>
            <div class="slot-row">
              <el-form-item label="到达时段">
                <el-select v-model="appointmentForm.arrival_slot">
                  <el-option
                    v-for="s in slotOptions"
                    :key="s.value"
                    :label="s.label"
                    :value="s.value"
                  />
                </el-select>
              </el-form-item>
              <el-form-item label="离开时段">
                <el-select v-model="appointmentForm.departure_slot">
                  <el-option
                    v-for="s in slotOptions"
                    :key="s.value"
                    :label="s.label"
                    :value="s.value"
                  />
                </el-select>
              </el-form-item>
            </div>
            <el-form-item label="来访原因">
              <el-input
                v-model="appointmentForm.visit_reason"
                type="textarea"
                :rows="3"
                placeholder="请填写来访事由"
              />
            </el-form-item>
            <el-button type="primary" :loading="submittingAppointment" @click="submitAppointment">
              提交预约
            </el-button>
          </el-form>
        </article>

        <article class="panel">
          <div class="panel-head">
            <span class="icon green"><el-icon><Search /></el-icon></span>
            <div>
              <h2>预约查询</h2>
              <p>凭身份证号查看审核状态。</p>
            </div>
          </div>
          <div class="lookup">
            <el-input v-model="lookupIdCard" maxlength="18" placeholder="18 位身份证号" />
            <el-button :loading="lookingUp" @click="lookupAppointments">查询</el-button>
          </div>
          <div v-if="appointments.length === 0" class="empty">暂无预约记录</div>
          <div v-else class="appointments">
            <div v-for="apt in appointments" :key="apt.id" class="apt-row">
              <div>
                <strong>{{ apt.arrival_date }} - {{ apt.departure_date }}</strong>
                <p>{{ slotOptions[apt.arrival_slot]?.label }} - {{ slotOptions[apt.departure_slot]?.label }}</p>
                <p>{{ apt.visit_reason }}</p>
                <p v-if="apt.status === 'rejected' && apt.reject_reason" class="apt-reject">
                  拒绝原因：{{ apt.reject_reason }}
                </p>
                <p v-if="apt.status === 'expired'" class="apt-expired">
                  该预约已超过有效通行时间，仅作为历史记录保留。
                </p>
              </div>
              <el-tag :type="statusType(apt.status)">{{ statusText(apt.status) }}</el-tag>
            </div>
          </div>
        </article>
      </section>
    </div>
  </main>
</template>

<style scoped>
.visitor-page {
  min-height: 100vh;
  background:
    linear-gradient(180deg, rgba(0, 61, 122, 0.08), rgba(212, 175, 55, 0.08)),
    #f4f8fb;
  color: #172033;
}

.visitor-shell {
  width: min(1180px, calc(100% - 32px));
  margin: 0 auto;
  padding: 28px 0 40px;
}

.visitor-head {
  display: flex;
  align-items: center;
  gap: 20px;
  margin-bottom: 24px;
}

.visitor-head h1 {
  margin: 0;
  font-size: 28px;
  line-height: 1.2;
  letter-spacing: 0;
}

.visitor-head p {
  margin: 6px 0 0;
  color: #637083;
}

.back {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-height: 36px;
  padding: 0 12px;
  border: 1px solid rgba(0, 61, 122, 0.14);
  border-radius: 999px;
  color: #003d7a;
  background: rgba(255, 255, 255, 0.72);
  cursor: pointer;
}

.grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 18px;
}

.panel {
  padding: 22px;
  border: 1px solid rgba(0, 61, 122, 0.08);
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.92);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.06);
}

.panel-head {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 18px;
}

.panel-head h2 {
  margin: 0;
  font-size: 17px;
  letter-spacing: 0;
}

.panel-head p {
  margin: 3px 0 0;
  color: #637083;
  font-size: 13px;
}

.icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 42px;
  height: 42px;
  border-radius: 12px;
  color: #fff;
  flex-shrink: 0;
}

.icon.blue { background: linear-gradient(135deg, #003d7a, #1565c0); }
.icon.gold { background: linear-gradient(135deg, #b8860b, #d4af37); }
.icon.red { background: linear-gradient(135deg, #8b0000, #b22222); }
.icon.green { background: linear-gradient(135deg, #2e7d5b, #43a047); }

.actions,
.lookup {
  display: flex;
  gap: 10px;
  margin-top: 14px;
  flex-wrap: wrap;
  align-items: center;
}

.result-line,
.empty {
  margin: 14px 0 0;
  color: #637083;
  font-size: 13px;
}

.slot-row {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.full-input {
  width: 100%;
}

.camera-box {
  position: relative;
  aspect-ratio: 4 / 3;
  overflow: hidden;
  border-radius: 14px;
  background: #0f172a;
}

.camera-box video {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.camera-box.is-off video {
  opacity: 0;
}

.camera-mask {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  color: rgba(255, 255, 255, 0.72);
}

.camera-mask p {
  margin: 0;
}

.frames {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(88px, 1fr));
  gap: 10px;
  margin-top: 14px;
}

.frame {
  position: relative;
  aspect-ratio: 4 / 3;
  overflow: hidden;
  border: 2px solid transparent;
  border-radius: 12px;
  cursor: pointer;
  background: #e5e7eb;
}

.frame img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.frame.is-selected {
  border-color: #003d7a;
}

.frame-check {
  position: absolute;
  top: 6px;
  left: 6px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  border-radius: 999px;
  color: #fff;
  background: #003d7a;
}

.frame-del {
  position: absolute;
  top: 4px;
  right: 4px;
  width: 22px;
  height: 22px;
  border: 0;
  border-radius: 999px;
  color: #fff;
  background: rgba(185, 28, 28, 0.86);
  cursor: pointer;
  line-height: 20px;
}

.upload-fallback {
  margin-top: 6px;
}

.appointments {
  display: grid;
  gap: 10px;
  margin-top: 14px;
}

.apt-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding: 12px;
  border-radius: 12px;
  background: #f8fafc;
}

.apt-row p {
  margin: 4px 0 0;
  color: #637083;
  font-size: 13px;
}

.apt-row .apt-reject {
  color: #b42318;
  font-weight: 600;
}

.apt-row .apt-expired {
  color: #7a869a;
}

@media (max-width: 860px) {
  .visitor-head,
  .grid {
    grid-template-columns: 1fr;
    display: grid;
  }

  .slot-row {
    grid-template-columns: 1fr;
  }

}
</style>
