<script setup lang="ts">
/** 人脸录入 · getUserMedia + 多帧抓取 / 照片上传 + /api/persons/{id}/faces。 */
import { Camera, Check, Delete, VideoCamera, VideoPause } from "@element-plus/icons-vue";
import { ElMessage } from "element-plus";

import { personsApi } from "@/api/persons";
import type { FaceRegisterSummary } from "@/api/persons";
import type { PersonOut } from "@/api/types";
import DataCard from "@/components/common/DataCard.vue";
import PageHeader from "@/components/common/PageHeader.vue";
import { CameraUnavailableError, closeCamera, openCamera } from "@/utils/camera";
import FaceUploadPanel from "./components/FaceUploadPanel.vue";

const route = useRoute();
const router = useRouter();

const videoRef = ref<HTMLVideoElement>();
const captureCanvas = document.createElement("canvas");

const personId = ref<number | null>(
  route.query.id ? Number(route.query.id) : null,
);
const person = ref<PersonOut | null>(null);
const personSearch = ref("");
const searchResults = ref<PersonOut[]>([]);
const captureCount = ref(5);
const intervalMs = ref(350);
const stream = ref<MediaStream | null>(null);
const cameraOn = computed(() => !!stream.value);
const capturing = ref(false);
const submitting = ref(false);
const result = ref<FaceRegisterSummary | null>(null);

type FaceCandidateSource = "camera" | "upload";

interface FaceCandidate {
  blob: Blob;
  url: string;
  selected: boolean;
  source: FaceCandidateSource;
  name?: string;
}

const previews = ref<FaceCandidate[]>([]);
const selectedCount = computed(() => previews.value.filter((p) => p.selected).length);

async function loadPerson() {
  if (!personId.value) {
    person.value = null;
    return;
  }
  try {
    person.value = await personsApi.get(personId.value);
  } catch {
    person.value = null;
  }
}
watch(personId, loadPerson, { immediate: true });

async function searchPerson() {
  if (!personSearch.value) {
    searchResults.value = [];
    return;
  }
  const r = await personsApi.list({ q: personSearch.value, page: 1, page_size: 8 });
  searchResults.value = r.items;
}

function pickPerson(p: PersonOut) {
  personId.value = p.id;
  searchResults.value = [];
  personSearch.value = "";
}

async function startCamera() {
  try {
    stream.value = await openCamera();
    if (videoRef.value) {
      videoRef.value.srcObject = stream.value;
      await videoRef.value.play();
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

function clearPreviews() {
  previews.value.forEach((p) => URL.revokeObjectURL(p.url));
  previews.value = [];
}

async function captureFrames() {
  if (!videoRef.value || !cameraOn.value) {
    ElMessage.warning("请先打开摄像头");
    return;
  }
  capturing.value = true;
  result.value = null;
  clearPreviews();

  const v = videoRef.value;
  captureCanvas.width = v.videoWidth;
  captureCanvas.height = v.videoHeight;
  const ctx = captureCanvas.getContext("2d");
  if (!ctx) { capturing.value = false; return; }

  for (let i = 0; i < captureCount.value; i++) {
    ctx.drawImage(v, 0, 0);
    const blob: Blob = await new Promise((resolve) =>
      captureCanvas.toBlob((b) => resolve(b!), "image/jpeg", 0.92),
    );
    const url = URL.createObjectURL(blob);
    previews.value.push({ blob, url, selected: true, source: "camera" });
    if (i < captureCount.value - 1) {
      await new Promise((r) => setTimeout(r, intervalMs.value));
    }
  }
  capturing.value = false;
  ElMessage.success(`已抓取 ${captureCount.value} 帧`);
}

function toggleFrame(i: number) {
  previews.value[i].selected = !previews.value[i].selected;
}
function removeFrame(i: number) {
  URL.revokeObjectURL(previews.value[i].url);
  previews.value.splice(i, 1);
}

function safeFileName(name: string): string {
  const cleaned = name.replace(/[^\w.-]+/g, "_").replace(/^_+|_+$/g, "");
  return cleaned && !cleaned.startsWith(".") ? cleaned : "upload.jpg";
}

function addUploadedFiles(files: File[]) {
  result.value = null;
  let added = 0;
  for (const file of files) {
    const url = URL.createObjectURL(file);
    previews.value.push({
      blob: file,
      url,
      selected: true,
      source: "upload",
      name: file.name,
    });
    added += 1;
  }
  if (added) ElMessage.success(`已添加 ${added} 张上传照片`);
}

async function submit() {
  if (!personId.value) { ElMessage.warning("请先选择目标人员"); return; }
  const selected = previews.value.filter((p) => p.selected);
  if (selected.length === 0) { ElMessage.warning("请勾选至少一张样本"); return; }

  submitting.value = true;
  try {
    const stamp = Date.now();
    const files = selected.map((p, i) => {
      if (p.blob instanceof File) {
        return new File([p.blob], safeFileName(p.blob.name || `upload_${stamp}_${i}.jpg`), {
          type: p.blob.type || "image/jpeg",
        });
      }
      return new File([p.blob], `camera_${stamp}_${i}.jpg`, { type: "image/jpeg" });
    });
    result.value = await personsApi.addFaces(personId.value, files);
    ElMessage.success(
      `入库 ${result.value.added}，重复 ${result.value.skipped_duplicates}，` +
      `无脸 ${result.value.skipped_no_face}，活体拒 ${result.value.skipped_spoof}，` +
      `质量拒 ${result.value.skipped_quality}`,
    );
    clearPreviews();
    loadPerson();
  } finally {
    submitting.value = false;
  }
}

onMounted(startCamera);
onBeforeUnmount(() => {
  stopCamera();
  clearPreviews();
});
</script>

<template>
  <div>
    <PageHeader
      title="人脸录入"
      subtitle="摄像头多帧采集 / 照片上传 · 后台活体与质量校验 · 入 FAISS 向量库"
    >
      <template #actions>
        <el-button v-if="!cameraOn" type="primary" :icon="VideoCamera" @click="startCamera">
          开启摄像头
        </el-button>
        <el-button v-else :icon="VideoPause" @click="stopCamera">关闭摄像头</el-button>
      </template>
    </PageHeader>

    <div class="grid">
      <DataCard>
        <template #header>
          <span class="head">实时画面</span>
          <span v-if="cameraOn" class="dim"><span class="live-dot" /> LIVE</span>
        </template>
        <div class="video-wrap" :class="!cameraOn && 'is-off'">
          <video ref="videoRef" muted playsinline />
          <div v-if="!cameraOn" class="off-mask">
            <el-icon :size="48"><VideoPause /></el-icon>
            <p>摄像头未开启</p>
          </div>
        </div>
        <div class="capture-bar">
          <span>抓取帧数</span>
          <el-input-number v-model="captureCount" :min="1" :max="20" size="small" />
          <span>间隔(ms)</span>
          <el-input-number v-model="intervalMs" :min="100" :max="2000" :step="50" size="small" />
          <el-button
            type="primary" :icon="Camera" :loading="capturing"
            :disabled="!cameraOn" @click="captureFrames"
          >抓取</el-button>
        </div>
      </DataCard>

      <DataCard>
        <template #header>
          <span class="head">目标人员</span>
        </template>
        <div v-if="person" class="target">
          <div class="avatar">{{ person.name.slice(0, 1) }}</div>
          <div class="meta">
            <div class="name">{{ person.name }}</div>
            <div class="dim">{{ person.external_id }} · {{ person.faculty_name || "—" }}</div>
            <div class="dim">已注册 {{ person.embedding_count }} 张</div>
          </div>
          <el-button link type="primary" size="small" @click="personId = null">更换</el-button>
        </div>
        <div v-else class="search">
          <el-input
            v-model="personSearch"
            placeholder="按学号或姓名搜索人员"
            clearable @input="searchPerson"
          />
          <div v-if="searchResults.length" class="results">
            <div v-for="r in searchResults" :key="r.id"
              class="result-row" @click="pickPerson(r)"
            >
              <div class="result-name">{{ r.name }}</div>
              <div class="dim mono">{{ r.external_id }}</div>
            </div>
          </div>
        </div>
      </DataCard>

      <DataCard class="full">
        <template #header>
          <span class="head">候选样本（已勾选的提交入库）</span>
          <div class="header-actions">
            <el-button
              :icon="Delete"
              :disabled="previews.length === 0"
              @click="clearPreviews"
            >
              清空
            </el-button>
            <el-button
              :disabled="!personId || selectedCount === 0"
              :loading="submitting" type="primary" @click="submit"
            >
              入库 · {{ selectedCount }} 张
            </el-button>
          </div>
        </template>
        <FaceUploadPanel class="upload-panel" @add-files="addUploadedFiles" />
        <div v-if="previews.length === 0" class="empty">
          <el-empty description="从摄像头抓取或上传照片后，在这里选择高质量样本入库" />
        </div>
        <div v-else class="frames">
          <div v-for="(p, i) in previews" :key="i"
            :class="['frame', p.selected && 'is-selected']"
            @click="toggleFrame(i)"
          >
            <img :src="p.url" :class="p.source === 'camera' && 'is-camera'" alt="" />
            <span :class="['frame-source', p.source]">
              {{ p.source === "camera" ? "摄像头" : "上传" }}
            </span>
            <span v-if="p.name" class="frame-name" :title="p.name">{{ p.name }}</span>
            <div class="frame-check">
              <el-icon v-if="p.selected" :size="14"><Check /></el-icon>
            </div>
            <el-button
              link type="danger" size="small" class="frame-del"
              @click.stop="removeFrame(i)"
            >×</el-button>
          </div>
        </div>
        <div v-if="result" class="result-bar">
          <span class="r-ok">入库 {{ result.added }}</span>
          <span>·</span>
          <span>重复 {{ result.skipped_duplicates }}</span>
          <span>·</span>
          <span>无脸 {{ result.skipped_no_face }}</span>
          <span>·</span>
          <span class="r-warn">活体拒 {{ result.skipped_spoof }}</span>
          <span>·</span>
          <span class="r-warn">质量拒 {{ result.skipped_quality }}</span>
          <el-button
            link type="primary" size="small"
            @click="() => router.push(`/persons/${personId}`)"
          >查看详情 →</el-button>
        </div>
      </DataCard>
    </div>
  </div>
</template>

<style scoped>
.grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
}
.full { grid-column: 1 / -1; }
.head { font-weight: 600; }
.dim { font-size: 12px; color: var(--swu-text-3); }
.mono { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
.header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.video-wrap {
  position: relative;
  background: #000;
  border-radius: 10px;
  overflow: hidden;
  aspect-ratio: 16 / 9;
}
.video-wrap video {
  width: 100%; height: 100%; object-fit: cover;
  transform: scaleX(-1);
}
.off-mask {
  position: absolute; inset: 0;
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  color: rgba(255,255,255,0.5); gap: 12px;
}

.capture-bar {
  display: flex; align-items: center; gap: 10px;
  margin-top: 14px;
  font-size: 12px;
  color: var(--swu-text-2);
}

.live-dot {
  display: inline-block; width: 8px; height: 8px; border-radius: 50%;
  background: #F5222D; margin-right: 4px;
  box-shadow: 0 0 6px #F5222D;
  animation: pulse 1.2s ease-in-out infinite;
}
@keyframes pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50%      { opacity: 0.45; transform: scale(0.85); }
}

.target { display: flex; align-items: center; gap: 12px; }
.avatar {
  width: 48px; height: 48px;
  background: linear-gradient(135deg, #003D7A, #1565C0);
  color: #fff; border-radius: 50%;
  display: inline-flex; align-items: center; justify-content: center;
  font-size: 20px; font-weight: 600;
}
.meta { flex: 1; }
.name { font-weight: 600; }

.search { display: flex; flex-direction: column; gap: 8px; }
.results { border: 1px solid var(--swu-border); border-radius: 8px; max-height: 260px; overflow-y: auto; }
.result-row { padding: 10px 12px; cursor: pointer; transition: background 0.12s ease; }
.result-row:hover { background: var(--swu-blue-50); }
.result-row + .result-row { border-top: 1px solid var(--swu-divider); }
.result-name { font-size: 13px; }

.upload-panel {
  margin-bottom: 16px;
}

.frames {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 10px;
}
.frame {
  position: relative;
  border-radius: 8px;
  overflow: hidden;
  cursor: pointer;
  border: 2px solid transparent;
  transition: border-color 0.15s ease, transform 0.12s ease;
}
.frame:hover { transform: translateY(-2px); }
.frame img {
  width: 100%; aspect-ratio: 16 / 9; object-fit: cover; display: block;
}
.frame img.is-camera {
  transform: scaleX(-1);
}
.frame.is-selected { border-color: var(--swu-blue); }
.frame.is-selected .frame-check { background: var(--swu-blue); color: #fff; }
.frame-source {
  position: absolute;
  left: 6px;
  bottom: 6px;
  padding: 3px 7px;
  border-radius: 999px;
  font-size: 11px;
  line-height: 1;
  font-weight: 600;
  color: #fff;
  background: rgba(0, 0, 0, 0.52);
  backdrop-filter: blur(6px);
}
.frame-source.upload {
  background: rgba(0, 61, 122, 0.82);
}
.frame-name {
  position: absolute;
  right: 6px;
  bottom: 6px;
  max-width: calc(100% - 72px);
  padding: 3px 7px;
  overflow: hidden;
  color: rgba(255, 255, 255, 0.92);
  background: rgba(0, 0, 0, 0.48);
  border-radius: 999px;
  font-size: 11px;
  line-height: 1;
  text-overflow: ellipsis;
  white-space: nowrap;
  backdrop-filter: blur(6px);
}
.frame-check {
  position: absolute; top: 6px; left: 6px;
  width: 22px; height: 22px;
  background: rgba(255,255,255,0.7);
  border-radius: 4px;
  display: inline-flex; align-items: center; justify-content: center;
  color: transparent;
}
.frame-del {
  position: absolute; top: 6px; right: 6px;
  background: rgba(0,0,0,0.5); color: #fff !important;
  width: 22px; height: 22px; padding: 0; line-height: 1;
}
.empty { padding: 30px 0; }

.result-bar {
  margin-top: 14px;
  padding: 10px 14px;
  background: var(--swu-blue-50);
  border-radius: 8px;
  display: flex; gap: 10px; align-items: center;
  font-size: 13px;
  flex-wrap: wrap;
}
.r-ok   { color: var(--swu-success); font-weight: 600; }
.r-warn { color: var(--swu-warning); font-weight: 600; }
</style>
