<script setup lang="ts">
import { useEventListener, usePreferredReducedMotion, useResizeObserver } from "@vueuse/core";
import { RefreshRight, WarningFilled } from "@element-plus/icons-vue";
import { gsap } from "gsap";
import { Vue3Lottie } from "vue3-lottie";
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from "vue";

import ExplainOverlay from "@/components/recognize/ExplainOverlay.vue";
import { useCameraStream } from "@/composables/useCameraStream";
import { type GateRecognitionResult, type TrackedFace, useGateRecognition } from "@/composables/useGateRecognition";
import { motionDurations, motionEase, swuMotionColors } from "@/styles/motion-tokens";

const props = defineProps<{
  gateId: number | null;
  gateCode?: string | null;
  gateName?: string;
  gateOnline?: boolean;
}>();

const emit = defineEmits<{
  (e: "result", result: GateRecognitionResult): void;
}>();

const overlayRef = ref<HTMLCanvasElement>();
const stageRef = ref<HTMLElement>();
const scanRingRef = ref<HTMLElement>();
const reducedMotion = usePreferredReducedMotion();

const camera = useCameraStream({ facingMode: "user", width: 1280, height: 720 });
const videoRef = camera.videoRef;
const recognitionEnabled = computed(() => Boolean(camera.cameraOk.value && props.gateId && props.gateOnline !== false));

const recognition = useGateRecognition({
  gateId: computed(() => props.gateId),
  gateCode: computed(() => props.gateCode),
  enabled: recognitionEnabled,
  sourceSize: () => camera.sourceSize.value,
  captureDataUrl: camera.captureDataUrl,
  captureBlob: camera.captureBlob,
  onResult: (result) => emit("result", result),
});

const animatedBox = reactive({ x: 0, y: 0, w: 0, h: 0, opacity: 0 });
let faceTween: gsap.core.Tween | null = null;
let ringTween: gsap.core.Tween | null = null;

const gateBlocked = computed(() => props.gateId != null && props.gateOnline === false);
const stateTone = computed(() => {
  if (recognition.phase.value === "verifying") return "verify";
  if (recognition.wsStatus.value === "reconnecting" || recognition.phase.value === "error") return "warn";
  if (recognition.repeatBlocked.value) return "done";
  return recognition.primaryFace.value ? "active" : "idle";
});

const stageHint = computed(() => {
  if (camera.cameraError.value) return camera.cameraError.value;
  if (gateBlocked.value) return "当前门禁离线，暂不进行自动核验";
  return recognition.statusText.value;
});

const faceColor = computed(() => {
  const face = recognition.primaryFace.value;
  if (recognition.phase.value === "verifying") return swuMotionColors.gold;
  if (!face) return swuMotionColors.primary;
  if (face.decision === "granted") return swuMotionColors.granted;
  if (face.decision === "spoof") return swuMotionColors.spoof;
  if (face.decision === "rejected") return swuMotionColors.rejected;
  return swuMotionColors.primary;
});

function mapBbox(face: TrackedFace) {
  const canvas = overlayRef.value;
  if (!canvas) return null;
  const rect = canvas.getBoundingClientRect();
  const source = camera.sourceSize.value;
  const scale = Math.max(rect.width / source.width, rect.height / source.height);
  const drawW = source.width * scale;
  const drawH = source.height * scale;
  const offsetX = (rect.width - drawW) / 2;
  const offsetY = (rect.height - drawH) / 2;
  const [x1, y1, x2, y2] = face.bbox;

  let left = offsetX + x1 * scale;
  let right = offsetX + x2 * scale;
  if (camera.mirrored.value) {
    left = rect.width - (offsetX + x2 * scale);
    right = rect.width - (offsetX + x1 * scale);
  }

  return {
    x: left,
    y: offsetY + y1 * scale,
    w: right - left,
    h: (y2 - y1) * scale,
  };
}

function roundRectPath(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, r: number) {
  const radius = Math.min(r, w / 2, h / 2);
  ctx.beginPath();
  ctx.moveTo(x + radius, y);
  ctx.lineTo(x + w - radius, y);
  ctx.quadraticCurveTo(x + w, y, x + w, y + radius);
  ctx.lineTo(x + w, y + h - radius);
  ctx.quadraticCurveTo(x + w, y + h, x + w - radius, y + h);
  ctx.lineTo(x + radius, y + h);
  ctx.quadraticCurveTo(x, y + h, x, y + h - radius);
  ctx.lineTo(x, y + radius);
  ctx.quadraticCurveTo(x, y, x + radius, y);
}

function drawOverlay() {
  const canvas = overlayRef.value;
  if (!canvas) return;
  const rect = canvas.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;
  canvas.width = Math.max(1, Math.round(rect.width * dpr));
  canvas.height = Math.max(1, Math.round(rect.height * dpr));
  const ctx = canvas.getContext("2d");
  if (!ctx) return;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, rect.width, rect.height);

  if (animatedBox.opacity <= 0.01) return;
  const color = faceColor.value;
  const { x, y, w, h, opacity } = animatedBox;
  const pad = Math.max(8, Math.min(w, h) * 0.04);

  ctx.save();
  ctx.globalAlpha = opacity;
  ctx.shadowBlur = 22;
  ctx.shadowColor = color;
  ctx.lineWidth = 3;
  ctx.strokeStyle = color;
  roundRectPath(ctx, x - pad, y - pad, w + pad * 2, h + pad * 2, 20);
  ctx.stroke();

  ctx.shadowBlur = 0;
  ctx.lineWidth = 5;
  ctx.strokeStyle = swuMotionColors.gold;
  const corner = Math.min(42, Math.max(22, Math.min(w, h) * 0.18));
  const x0 = x - pad;
  const y0 = y - pad;
  const x1 = x + w + pad;
  const y1 = y + h + pad;
  ctx.beginPath();
  ctx.moveTo(x0 + corner, y0); ctx.lineTo(x0, y0); ctx.lineTo(x0, y0 + corner);
  ctx.moveTo(x1 - corner, y0); ctx.lineTo(x1, y0); ctx.lineTo(x1, y0 + corner);
  ctx.moveTo(x0, y1 - corner); ctx.lineTo(x0, y1); ctx.lineTo(x0 + corner, y1);
  ctx.moveTo(x1 - corner, y1); ctx.lineTo(x1, y1); ctx.lineTo(x1, y1 - corner);
  ctx.stroke();

  const label = recognition.phase.value === "verifying"
    ? "核验锁定"
    : recognition.repeatBlocked.value
      ? "已核验"
      : "人脸追踪";
  ctx.font = "700 13px 'PingFang SC', 'Microsoft YaHei', sans-serif";
  const labelW = ctx.measureText(label).width + 22;
  const labelX = Math.max(10, Math.min(rect.width - labelW - 10, x0));
  const labelY = Math.max(28, y0 - 12);
  ctx.fillStyle = "rgba(0, 20, 40, 0.78)";
  roundRectPath(ctx, labelX, labelY - 22, labelW, 26, 13);
  ctx.fill();
  ctx.fillStyle = "#fff";
  ctx.fillText(label, labelX + 11, labelY - 5);
  ctx.restore();
}

function animateFace(face: TrackedFace | null) {
  faceTween?.kill();
  if (!face) {
    faceTween = gsap.to(animatedBox, {
      opacity: 0,
      duration: reducedMotion.value === "reduce" ? 0 : motionDurations.fast,
      ease: motionEase.standard,
      onUpdate: drawOverlay,
      onComplete: drawOverlay,
    });
    return;
  }
  const mapped = mapBbox(face);
  if (!mapped) return;
  faceTween = gsap.to(animatedBox, {
    ...mapped,
    opacity: 1,
    duration: reducedMotion.value === "reduce" ? 0 : motionDurations.base,
    ease: motionEase.standard,
    overwrite: true,
    onUpdate: drawOverlay,
  });
}

function animateRing() {
  ringTween?.kill();
  ringTween = null;
}

watch(() => recognition.primaryFace.value, animateFace);
watch([() => recognition.phase.value, () => recognition.repeatBlocked.value], drawOverlay);
useResizeObserver(stageRef, drawOverlay);
useEventListener(window, "resize", drawOverlay);

onMounted(async () => {
  await camera.start();
  await nextTick();
  animateRing();
  drawOverlay();
});

onBeforeUnmount(() => {
  faceTween?.kill();
  ringTween?.kill();
  recognition.stop();
});
</script>

<template>
  <div ref="stageRef" class="camera-stage" :class="[`is-${stateTone}`, { 'is-mirrored': camera.mirrored.value }]">
    <div class="recognition-layout">
      <section class="video-column" aria-label="人脸识别摄像头">
        <div class="video-wrap">
          <video ref="videoRef" muted playsinline autoplay class="video" />
          <canvas ref="overlayRef" class="bbox-canvas" />

          <div ref="scanRingRef" class="scanner-ring" :class="recognition.phase.value">
            <Vue3Lottie
              animation-link="/lottie/face-scan.json"
              :height="450"
              :width="450"
              :loop="true"
              :auto-play="recognition.phase.value === 'idle' || recognition.phase.value === 'detecting'"
              no-margin
            />
          </div>

          <div class="scan-line" :class="{ active: recognition.phase.value === 'verifying' }" />
          <div class="grain" />

          <div v-if="camera.starting.value" class="system-mask">
            <div class="pulse-dot" />
            <strong>正在开启摄像头…</strong>
            <span>请允许浏览器访问摄像头</span>
          </div>

          <div v-else-if="camera.cameraError.value" class="system-mask is-error">
            <el-icon :size="34"><WarningFilled /></el-icon>
            <strong>摄像头不可用</strong>
            <span>{{ camera.cameraError.value }}</span>
            <el-button :icon="RefreshRight" type="primary" plain @click="camera.retry">重试</el-button>
          </div>

          <div v-else-if="gateBlocked" class="system-mask is-error">
            <el-icon :size="34"><WarningFilled /></el-icon>
            <strong>门禁离线</strong>
            <span>请联系门卫或管理员检查设备状态</span>
          </div>

          <div class="hud-top">
            <span class="chip" :class="recognition.wsStatus.value">{{ recognition.wsStatus.value === 'open' ? '识别在线' : '连接中' }}</span>
            <span class="chip dim">{{ recognition.fps.value || 0 }} fps</span>
          </div>

          <div class="hud-bottom">
            <strong>{{ stageHint }}</strong>
            <span>{{ gateName || '当前门禁' }} · 阈值 {{ recognition.threshold.value.toFixed(2) }}</span>
          </div>
        </div>
      </section>

      <aside class="pipeline-column" aria-label="流水线可视化">
        <ExplainOverlay
          panel
          :show-canvas="false"
          :face="recognition.primaryFace.value"
          :source-size="camera.sourceSize.value"
          :mirrored="camera.mirrored.value"
          :phase="recognition.phase.value"
          :threshold="recognition.threshold.value"
          :enabled="recognitionEnabled"
        />
      </aside>
    </div>
  </div>
</template>

<style scoped>
.camera-stage {
  --stage-blue: #003d7a;
  --stage-gold: #d4af37;
  position: relative;
}

.recognition-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(320px, 380px);
  gap: 22px;
  align-items: stretch;
}

.video-column,
.pipeline-column {
  min-width: 0;
}

.pipeline-column {
  min-height: clamp(520px, calc(100vh - 160px), 720px);
}

.video-wrap {
  position: relative;
  height: clamp(520px, calc(100vh - 160px), 720px);
  min-height: 520px;
  border: 1px solid rgba(0, 61, 122, 0.22);
  border-radius: 28px;
  overflow: hidden;
  background:
    radial-gradient(circle at 50% 35%, rgba(0, 61, 122, 0.24), transparent 42%),
    linear-gradient(145deg, #04111f, #0a2340 55%, #040b14);
  box-shadow:
    0 24px 70px rgba(0, 35, 76, 0.24),
    inset 0 0 0 1px rgba(255, 255, 255, 0.06);
}

.video {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
  opacity: 0.94;
}

.is-mirrored .video {
  transform: scaleX(-1);
}

.bbox-canvas,
.grain,
.scan-line,
.scanner-ring {
  position: absolute;
  inset: 0;
  pointer-events: none;
}

.bbox-canvas {
  width: 100%;
  height: 100%;
  z-index: 4;
}

.grain {
  z-index: 2;
  opacity: 0.18;
  background-image:
    linear-gradient(rgba(255,255,255,0.08) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255,255,255,0.06) 1px, transparent 1px);
  background-size: 34px 34px;
  mix-blend-mode: screen;
}

.scanner-ring {
  z-index: 3;
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0.62;
  filter: drop-shadow(0 0 18px rgba(0, 61, 122, 0.5));
}

.scanner-ring.verifying {
  opacity: 0.95;
  filter: drop-shadow(0 0 28px rgba(212, 175, 55, 0.74));
}

.scan-line {
  z-index: 3;
  opacity: 0;
  background: linear-gradient(180deg, transparent, rgba(212, 175, 55, 0.86), transparent);
  height: 22%;
  transform: translateY(-100%);
}

.scan-line.active {
  opacity: 0.72;
  animation: scan-pass 1.15s ease-in-out infinite;
}

@keyframes scan-pass {
  from { transform: translateY(-100%); }
  to { transform: translateY(460%); }
}

.system-mask {
  position: absolute;
  inset: 0;
  z-index: 8;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 28px;
  text-align: center;
  color: #fff;
  background: rgba(1, 15, 30, 0.72);
  backdrop-filter: blur(10px);
}

.system-mask strong {
  font-size: 22px;
  letter-spacing: 0.04em;
}

.system-mask span {
  max-width: 420px;
  color: rgba(255, 255, 255, 0.72);
  line-height: 1.6;
}

.system-mask.is-error {
  color: #fee2e2;
}

.pulse-dot {
  width: 18px;
  height: 18px;
  border-radius: 999px;
  background: var(--stage-gold);
  box-shadow: 0 0 0 0 rgba(212, 175, 55, 0.5);
  animation: pulse-dot 1.4s ease-out infinite;
}

@keyframes pulse-dot {
  to { box-shadow: 0 0 0 28px rgba(212, 175, 55, 0); }
}

.hud-top,
.hud-bottom {
  position: absolute;
  left: 18px;
  right: 18px;
  z-index: 6;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.hud-top { top: 16px; }
.hud-bottom {
  bottom: 16px;
  align-items: flex-end;
  padding: 16px 18px;
  border: 1px solid rgba(255,255,255,0.14);
  border-radius: 18px;
  color: #fff;
  background: linear-gradient(90deg, rgba(0, 25, 55, 0.72), rgba(0, 61, 122, 0.44));
  backdrop-filter: blur(8px);
}

.hud-bottom strong {
  font-size: clamp(18px, 3vw, 26px);
  letter-spacing: 0.03em;
}

.hud-bottom span {
  color: rgba(255,255,255,0.68);
  white-space: nowrap;
}

.chip {
  display: inline-flex;
  align-items: center;
  min-height: 30px;
  padding: 0 12px;
  border-radius: 999px;
  color: #fff;
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.06em;
  background: rgba(0, 61, 122, 0.76);
  box-shadow: 0 8px 24px rgba(0, 61, 122, 0.22);
}

.chip.open { background: rgba(32, 195, 107, 0.72); }
.chip.reconnecting,
.chip.connecting { background: rgba(249, 115, 22, 0.78); }
.chip.dim { background: rgba(15, 23, 42, 0.62); }

.is-warn .video-wrap { border-color: rgba(249, 115, 22, 0.42); }
.is-done .video-wrap { border-color: rgba(32, 195, 107, 0.5); }
.is-verify .video-wrap { border-color: rgba(212, 175, 55, 0.68); }

@media (max-width: 980px) {
  .recognition-layout {
    grid-template-columns: 1fr;
  }

  .pipeline-column {
    min-height: 360px;
  }

  .video-wrap {
    height: clamp(420px, 62vh, 620px);
    min-height: 420px;
  }
}

@media (max-width: 680px) {
  .video-wrap {
    height: 58vh;
    min-height: 360px;
    border-radius: 22px;
  }
  .pipeline-column { min-height: 340px; }
  .hud-bottom {
    align-items: flex-start;
    flex-direction: column;
  }
  .hud-bottom span { white-space: normal; }
}

@media (prefers-reduced-motion: reduce) {
  .scan-line.active,
  .pulse-dot {
    animation: none;
  }
}
</style>
