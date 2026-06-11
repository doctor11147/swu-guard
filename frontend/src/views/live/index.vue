<script setup lang="ts">
/** 实时监控 · 摄像头 → WS /api/ws/recognize → bbox 叠加 + 事件流。
 *  借鉴 MVP app/frontend/app.js 的核心逻辑，移植到 TS + Vue 3.5。
 */
import { VideoCamera, VideoPause, VideoPlay } from "@element-plus/icons-vue";
import { ElMessage } from "element-plus";

import { gatesApi } from "@/api/gates";
import { systemApi } from "@/api/system";
import type { AccessDecision, GateOut } from "@/api/types";
import DataCard from "@/components/common/DataCard.vue";
import PageHeader from "@/components/common/PageHeader.vue";
import { CameraUnavailableError, closeCamera, openCamera } from "@/utils/camera";

import PerfPanel from "./components/PerfPanel.vue";
import StageWaterfall from "./components/StageWaterfall.vue";
import { usePerfMonitor } from "./composables/usePerfMonitor";

interface FaceOut {
  bbox: [number, number, number, number];
  score: number;
  spoof_score: number | null;
  is_real: boolean | null;
  decision: AccessDecision;
  match: { person_id: number; student_id: string; name: string; score: number } | null;
}

interface FrameEvent {
  ts: string;
  faces: FaceOut[];
  threshold: number;
  timing?: ServerTiming;
}

interface ServerTiming {
  detect?: number;
  align?: number;
  liveness?: number;
  quality?: number;
  embed?: number;
  retrieve?: number;
  total?: number;
}

const videoRef = ref<HTMLVideoElement>();
const overlayRef = ref<HTMLCanvasElement>();
const captureCanvas = document.createElement("canvas");

const stream = ref<MediaStream | null>(null);
const cameraOn = computed(() => !!stream.value);
const streaming = ref(false);
const fps = ref(0);
const events = ref<FrameEvent[]>([]);
const lastFaces = ref<FaceOut[]>([]);
const latestTiming = ref<ServerTiming | null>(null);
const threshold = ref(0.4);
const perfMonitor = usePerfMonitor();

const gates = ref<GateOut[]>([]);
const gateCode = ref<string>("");

let ws: WebSocket | null = null;
let loopTimer: number | null = null;
let inflight = false;
let lastSendTs = 0;

const decisionLabel: Record<string, string> = {
  granted: "通行", rejected: "未识别", spoof: "活体拒", no_face: "无脸",
};
const decisionColor: Record<string, string> = {
  granted: "#52C41A", rejected: "#F5222D", spoof: "#FAAD14", no_face: "#8C8C8C",
};

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

function captureJPEG(quality = 0.55): string | null {
  const v = videoRef.value;
  if (!v || !v.videoWidth) return null;
  captureCanvas.width = v.videoWidth;
  captureCanvas.height = v.videoHeight;
  const ctx = captureCanvas.getContext("2d");
  if (!ctx) return null;
  ctx.drawImage(v, 0, 0);
  return captureCanvas.toDataURL("image/jpeg", quality);
}

function drawOverlay() {
  const v = videoRef.value;
  const c = overlayRef.value;
  if (!v || !c) return;
  c.width = v.clientWidth;
  c.height = v.clientHeight;
  const ctx = c.getContext("2d");
  if (!ctx) return;
  ctx.clearRect(0, 0, c.width, c.height);
  // CSS scaleX(-1) 镜像，bbox 需要随之反射
  const sx = c.width / (v.videoWidth || 1);
  const sy = c.height / (v.videoHeight || 1);
  for (const f of lastFaces.value) {
    const color = decisionColor[f.decision] ?? "#8C8C8C";
    // 原 bbox: 左上 (x1,y1) - 右下 (x2,y2)
    let [x1, y1, x2, y2] = f.bbox;
    // 视频被镜像翻转：转换 x 坐标
    const w = v.videoWidth;
    [x1, x2] = [w - x2, w - x1];
    const sx1 = x1 * sx, sy1 = y1 * sy;
    const w2 = (x2 - x1) * sx, h2 = (y2 - y1) * sy;
    ctx.lineWidth = 3;
    ctx.strokeStyle = color;
    ctx.strokeRect(sx1, sy1, w2, h2);

    const label = f.decision === "granted"
      ? `${f.match?.name} · ${f.match?.score.toFixed(2)}`
      : f.decision === "spoof"
        ? `攻击 ${f.spoof_score?.toFixed(2) ?? ""}`
        : decisionLabel[f.decision] ?? f.decision;

    // 标签底
    ctx.fillStyle = color;
    ctx.font = "13px ui-sans-serif, system-ui";
    const tx = sx1, ty = Math.max(16, sy1 - 6);
    const metrics = ctx.measureText(label);
    ctx.fillRect(tx, ty - 13, metrics.width + 10, 18);
    ctx.fillStyle = "#fff";
    ctx.fillText(label, tx + 5, ty);
  }
}

function openWS() {
  const proto = location.protocol === "https:" ? "wss:" : "ws:";
  ws = new WebSocket(`${proto}//${location.host}/api/ws/recognize`);
  ws.onerror = () => {
    ElMessage.error("识别服务连接失败，请确认后端 uvicorn 正在运行");
    stopStream();
  };
  ws.onmessage = (ev) => {
    inflight = false;
    perfMonitor.markReceived();
    try {
      const data: FrameEvent & { error?: string } = JSON.parse(ev.data);
      if (data.error) {
        ElMessage.warning(`识别失败：${data.error}`);
        return;
      }
      lastFaces.value = data.faces || [];
      latestTiming.value = data.timing ?? null;
      if (data.threshold != null) threshold.value = data.threshold;
      // 事件流去重：连续的相同决策 + 同人合并显示（避免高 fps 下刷屏）
      const cur = data.faces?.[0];
      const last = events.value[0]?.faces?.[0];
      const isSameAsLast =
        cur && last &&
        cur.decision === last.decision &&
        (cur.match?.person_id ?? null) === (last.match?.person_id ?? null);
      if (cur && !isSameAsLast) {
        const d = new Date();
        const tsLocal = `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')} ${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}:${String(d.getSeconds()).padStart(2,'0')}`;
        events.value.unshift({
          ts: tsLocal,
          faces: data.faces,
          threshold: data.threshold,
        });
        if (events.value.length > 30) events.value.length = 30;
      }
      drawOverlay();
      const now = performance.now();
      if (lastSendTs) fps.value = Math.round(1000 / (now - lastSendTs));
      lastSendTs = now;
    } catch { /* ignore */ }
  };
  ws.onclose = () => {
    streaming.value = false;
    inflight = false;
  };
}

function loop() {
  if (!streaming.value) return;
  if (!inflight && ws && ws.readyState === WebSocket.OPEN) {
    const dataUrl = captureJPEG();
    if (dataUrl) {
      perfMonitor.markSent();
      ws.send(JSON.stringify({ image: dataUrl, gate_code: gateCode.value || undefined }));
      inflight = true;
    }
  }
  loopTimer = window.setTimeout(loop, 100);
}

async function startStream() {
  if (!cameraOn.value) await startCamera();
  if (!cameraOn.value) return;
  perfMonitor.reset();
  openWS();
  streaming.value = true;
  ws!.onopen = () => {
    loop();
  };
}
function stopStream() {
  streaming.value = false;
  if (loopTimer) { clearTimeout(loopTimer); loopTimer = null; }
  ws?.close(); ws = null;
  lastFaces.value = [];
  latestTiming.value = null;
  fps.value = 0;
  perfMonitor.reset();
  // 清掉覆盖层
  const c = overlayRef.value;
  if (c) c.getContext("2d")?.clearRect(0, 0, c.width, c.height);
}

async function loadGates() { gates.value = await gatesApi.list(); }
async function loadThreshold() {
  try {
    const c = await systemApi.getConfig("recognition.match_threshold");
    threshold.value = (c.value_json?.value as number) ?? 0.4;
  } catch { /* ignore */ }
}

async function updateThreshold(v: number | undefined) {
  if (v == null) return;
  await systemApi.setConfig("recognition.match_threshold", v);
  threshold.value = v;
  ElMessage.success(`阈值已更新为 ${v.toFixed(2)}`);
}

onMounted(async () => {
  await Promise.all([loadGates(), loadThreshold(), startCamera()]);
});
onBeforeUnmount(() => {
  stopStream();
  stopCamera();
});

watch(() => videoRef.value, () => drawOverlay());
useEventListener(window, "resize", () => drawOverlay());
</script>

<template>
  <div>
    <PageHeader title="实时监控" subtitle="摄像头 → WebSocket → 端到端识别 + 活体校验">
      <template #actions>
        <el-button v-if="!cameraOn" type="primary" :icon="VideoCamera" @click="startCamera">
          打开摄像头
        </el-button>
        <el-button v-else :icon="VideoPause" @click="() => { stopStream(); stopCamera(); }">关闭</el-button>
      </template>
    </PageHeader>

    <div class="grid">
      <DataCard>
        <template #header>
          <span class="head">实时画面</span>
          <span v-if="streaming" class="dim live-tag">
            <span class="live-dot" /> 识别中 · {{ fps }} fps
          </span>
        </template>

        <div class="video-wrap" :class="!cameraOn && 'is-off'">
          <video ref="videoRef" muted playsinline />
          <canvas ref="overlayRef" class="overlay" />
          <div v-if="!cameraOn" class="off-mask">
            <el-icon :size="48"><VideoPause /></el-icon>
            <p>摄像头未开启</p>
          </div>
        </div>

        <div class="control-bar">
          <el-button
            v-if="!streaming"
            type="primary" :icon="VideoPlay"
            :disabled="!cameraOn"
            @click="startStream"
          >开始识别</el-button>
          <el-button v-else type="danger" @click="stopStream">停止</el-button>

          <el-select
            v-model="gateCode" placeholder="关联门禁（可选）"
            clearable style="width: 220px"
          >
            <el-option
              v-for="g in gates" :key="g.code"
              :label="g.name" :value="g.code"
            />
          </el-select>

          <div class="thr">
            <span>阈值</span>
            <el-slider
              :model-value="threshold"
              :min="0" :max="1" :step="0.01"
              style="width: 200px"
              @change="(v) => updateThreshold(v as number)"
            />
            <span class="thr-val">{{ threshold.toFixed(2) }}</span>
          </div>
        </div>
      </DataCard>

      <DataCard>
        <template #header>
          <span class="head">识别事件</span>
          <span class="dim">最近 30 帧</span>
        </template>
        <div v-if="events.length === 0" class="empty">
          <el-empty description="点击「开始识别」启动 WebSocket 流" />
        </div>
        <div v-else class="event-list">
          <div v-for="(ev, idx) in events" :key="idx" class="event">
            <div class="event-time">{{ ev.ts.slice(11, 19) }}</div>
            <div class="event-faces">
              <div
                v-for="(f, j) in ev.faces" :key="j"
                :class="['ev-face', `ev-${f.decision}`]"
              >
                <template v-if="f.decision === 'granted'">
                  ✅ <strong>{{ f.match?.name }}</strong>
                  <span class="ev-meta">{{ f.match?.student_id }} · {{ f.match?.score.toFixed(3) }}</span>
                </template>
                <template v-else-if="f.decision === 'spoof'">
                  ⚠️ <strong>活体拒</strong>
                  <span class="ev-meta">real={{ f.spoof_score?.toFixed(3) }}</span>
                </template>
                <template v-else-if="f.decision === 'rejected'">
                  ❌ <strong>未识别</strong>
                  <span v-if="f.match" class="ev-meta">
                    最近 {{ f.match.name }} ({{ f.match.score.toFixed(3) }})
                  </span>
                </template>
                <template v-else>
                  · {{ decisionLabel[f.decision] }}
                </template>
              </div>
            </div>
          </div>
        </div>
      </DataCard>
    </div>

    <PerfPanel :monitor="perfMonitor" :streaming="streaming" />
    <StageWaterfall :timing="latestTiming" :streaming="streaming" />
  </div>
</template>

<style scoped>
.grid {
  display: grid;
  grid-template-columns: 1.5fr 1fr;
  gap: 14px;
}
@media (max-width: 1100px) { .grid { grid-template-columns: 1fr; } }

.head { font-weight: 600; }
.dim { font-size: 12px; color: var(--swu-text-3); }
.live-tag { color: var(--swu-success); font-weight: 500; }

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
.video-wrap .overlay {
  position: absolute; inset: 0;
  width: 100%; height: 100%;
  pointer-events: none;
}
.off-mask {
  position: absolute; inset: 0;
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  color: rgba(255,255,255,0.5); gap: 12px;
}
.live-dot {
  display: inline-block; width: 8px; height: 8px; border-radius: 50%;
  background: #52C41A; margin-right: 6px;
  box-shadow: 0 0 6px #52C41A;
  animation: pulse 1.2s ease-in-out infinite;
}
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50%      { opacity: 0.45; }
}

.control-bar {
  display: flex; align-items: center; gap: 12px;
  margin-top: 14px;
  padding-top: 14px;
  border-top: 1px solid var(--swu-divider);
  flex-wrap: wrap;
}
.thr { display: flex; align-items: center; gap: 10px; font-size: 12px; color: var(--swu-text-2); }
.thr-val {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  color: var(--swu-blue); background: var(--swu-blue-50);
  padding: 2px 8px; border-radius: 4px;
}

.event-list { display: flex; flex-direction: column; gap: 8px; max-height: 520px; overflow-y: auto; }
.event {
  display: flex; gap: 10px; align-items: flex-start;
  padding: 8px 10px;
  border-radius: 8px;
  background: var(--swu-bg);
  font-size: 12px;
}
.event-time {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  color: var(--swu-text-3); flex-shrink: 0;
}
.event-faces { display: flex; flex-direction: column; gap: 4px; flex: 1; }
.ev-face {
  display: flex; align-items: center; gap: 6px;
  padding: 4px 8px;
  border-radius: 6px;
  line-height: 1.4;
}
.ev-granted  { background: rgba(82,196,26,0.08); color: var(--swu-text); }
.ev-rejected { background: rgba(245,34,45,0.06); color: var(--swu-text); }
.ev-spoof    { background: rgba(250,173,20,0.08); color: var(--swu-text); }
.ev-no_face  { background: rgba(140,140,140,0.06); }
.ev-meta { color: var(--swu-text-3); margin-left: auto; font-size: 11px; }

.empty { padding: 40px 0; }
</style>
