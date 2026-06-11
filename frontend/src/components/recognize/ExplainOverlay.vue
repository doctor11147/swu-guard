<script setup lang="ts">
import NumberFlow from "@number-flow/vue";
import type { Format } from "@number-flow/vue";
import { usePreferredReducedMotion } from "@vueuse/core";
import { computed, onBeforeUnmount, onMounted, reactive, ref } from "vue";

import { swuMotionColors } from "@/styles/motion-tokens";

type Decision = "granted" | "rejected" | "spoof" | "no_face";

interface SourceSize {
  width: number;
  height: number;
}

interface ExplainMatch {
  score?: number | null;
  name?: string | null;
}

interface ExplainFace {
  bbox?: number[] | [number, number, number, number];
  score?: number | null;
  spoofScore?: number | null;
  spoof_score?: number | null;
  isReal?: boolean | null;
  is_real?: boolean | null;
  decision?: Decision;
  match?: ExplainMatch | null;
  matchName?: string | null;
  quality_score?: number | null;
  qualityScore?: number | null;
  quality_adjusted_threshold?: number | null;
  qualityAdjustedThreshold?: number | null;
  runtime_thresholds?: Record<string, unknown> | null;
  kps?: number[] | number[][] | null;
  keypoints?: number[] | number[][] | null;
  landmarks?: number[] | number[][] | null;
}

const props = withDefaults(defineProps<{
  face: ExplainFace | null;
  sourceSize: SourceSize;
  mirrored?: boolean;
  phase?: string;
  threshold?: number;
  enabled?: boolean;
  panel?: boolean;
  showCanvas?: boolean;
}>(), {
  mirrored: false,
  phase: "idle",
  threshold: 0.4,
  enabled: true,
  panel: false,
  showCanvas: true,
});

const rootRef = ref<HTMLElement>();
const canvasRef = ref<HTMLCanvasElement>();
const overlayVisible = ref(true);
const reducedMotion = usePreferredReducedMotion();

const stageSize = reactive({ width: 1, height: 1 });
const targetBox = reactive({ x: 0, y: 0, w: 0, h: 0, opacity: 0 });
const renderBox = reactive({ x: 0, y: 0, w: 0, h: 0, opacity: 0 });

let rafId: number | null = null;
let resizeObserver: ResizeObserver | null = null;

const percentFormat = computed<Format>(() => ({
  notation: "standard",
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
}));
const probabilityFormat = computed<Format>(() => ({
  notation: "standard",
  minimumFractionDigits: 4,
  maximumFractionDigits: 4,
}));
const shouldReduceMotion = computed(() => reducedMotion.value === "reduce");

const normalizedBbox = computed<[number, number, number, number] | null>(() => {
  const bbox = props.face?.bbox;
  if (!bbox || bbox.length < 4) return null;
  const [x1, y1, x2, y2] = Array.from(bbox).map(Number);
  if (![x1, y1, x2, y2].every(Number.isFinite) || x2 <= x1 || y2 <= y1) return null;
  return [x1, y1, x2, y2];
});

function extractKeypointPairs(raw: ExplainFace["kps"] | ExplainFace["keypoints"] | ExplainFace["landmarks"]) {
  if (!raw) return [];
  const pairs: Array<[number, number]> = [];
  const points = raw as unknown[];

  if (Array.isArray(points[0])) {
    for (const point of raw as number[][]) {
      if (point.length >= 2) pairs.push([Number(point[0]), Number(point[1])]);
    }
  } else {
    const flat = raw as number[];
    for (let i = 0; i + 1 < flat.length; i += 2) pairs.push([Number(flat[i]), Number(flat[i + 1])]);
  }

  return pairs.filter(([x, y]) => Number.isFinite(x) && Number.isFinite(y)).slice(0, 5);
}

const keypointPairs = computed(() => extractKeypointPairs(props.face?.kps ?? props.face?.keypoints ?? props.face?.landmarks));

const mappedKeypoints = computed(() => {
  return keypointPairs.value
    .map(([x, y]) => mapPoint(x, y))
    .filter((point): point is { x: number; y: number } => Boolean(point));
});

const spoofScore = computed(() => props.face?.spoofScore ?? props.face?.spoof_score ?? null);
const qualityScore = computed(() => props.face?.qualityScore ?? props.face?.quality_score ?? null);
const matchScore = computed(() => props.face?.match?.score ?? null);
const detectorScore = computed(() => props.face?.score ?? null);
const detectorPercent = computed(() => rawScore(detectorScore.value));
const spoofPercent = computed(() => toPercent(spoofScore.value));
const livenessValue = computed(() => normalizeProbability(spoofScore.value));
const qualityPercent = computed(() => rawScore(qualityScore.value));
const matchPercent = computed(() => rawScore(matchScore.value));
const qualityAdjustedThreshold = computed(() => props.face?.qualityAdjustedThreshold ?? props.face?.quality_adjusted_threshold ?? null);
const isLiveAttack = computed(() => props.face?.decision === "spoof" || props.face?.isReal === false || props.face?.is_real === false);

const decisionMeta = computed(() => {
  if (!props.enabled) return { label: "OFFLINE", text: "未就绪", color: swuMotionColors.gold };
  if (!props.face || !normalizedBbox.value) return { label: "WAITING", text: "待检测", color: swuMotionColors.primary };
  switch (props.face?.decision) {
    case "granted":
      return { label: "GRANTED", text: "通行", color: swuMotionColors.granted };
    case "spoof":
      return { label: "SPOOF", text: "非真人", color: swuMotionColors.spoof };
    case "rejected":
      return { label: "REJECTED", text: "拒绝", color: swuMotionColors.rejected };
    case "no_face":
      return { label: "NO FACE", text: "无脸", color: swuMotionColors.gold };
    default:
      return { label: "TRACKING", text: "追踪", color: swuMotionColors.primary };
  }
});

const visibleFace = computed(() => Boolean(props.enabled && overlayVisible.value && normalizedBbox.value));
const showCard = computed(() => props.panel || visibleFace.value);
const matchName = computed(() => {
  if (!props.enabled) return "等待门禁与摄像头就绪";
  if (!normalizedBbox.value) return "等待正脸进入识别框";
  return props.face?.matchName || props.face?.match?.name || "未匹配身份";
});
const thresholdText = computed(() => (qualityAdjustedThreshold.value ?? props.threshold).toFixed(2));
const keypointText = computed(() => (keypointPairs.value.length ? `${keypointPairs.value.length}/5` : "待检测"));
const phaseLabel = computed(() => {
  const labels: Record<string, string> = {
    idle: "待机",
    detecting: "检测中",
    verifying: "核验中",
    result: "已出结果",
    cooldown: "冷却",
    reconnecting: "重连中",
    paused: "已暂停",
    error: "异常",
  };
  return labels[props.phase || "idle"] ?? props.phase;
});

const cardStyle = computed(() => {
  const width = stageSize.width;
  const cardW = 238;
  const gap = 14;
  const rightX = targetBox.x + targetBox.w + gap;
  const leftX = targetBox.x - cardW - gap;
  const placeLeft = rightX + cardW > width - 12 && leftX > 12;
  const x = Math.max(12, Math.min(width - cardW - 12, placeLeft ? leftX : rightX));
  const y = Math.max(54, Math.min(stageSize.height - 196, targetBox.y - 10));
  return {
    width: `${cardW}px`,
    transform: `translate3d(${x}px, ${y}px, 0)`,
    borderColor: decisionMeta.value.color,
  };
});

function toPercent(value: number | null | undefined): number | null {
  if (value == null || !Number.isFinite(Number(value))) return null;
  const n = Number(value);
  return Math.max(0, Math.min(100, Math.abs(n) <= 1 ? n * 100 : n));
}

function normalizeProbability(value: number | null | undefined): number | null {
  if (value == null || !Number.isFinite(Number(value))) return null;
  return Math.max(0, Math.min(1, Number(value)));
}

function rawScore(value: number | null | undefined): number | null {
  if (value == null || !Number.isFinite(Number(value))) return null;
  return Math.abs(Number(value)) <= 1 ? Number(value) * 100 : Number(value);
}

function mapPoint(x: number, y: number) {
  const source = props.sourceSize;
  if (!source.width || !source.height || !Number.isFinite(x) || !Number.isFinite(y)) return null;
  const scale = Math.max(stageSize.width / source.width, stageSize.height / source.height);
  const drawW = source.width * scale;
  const drawH = source.height * scale;
  const offsetX = (stageSize.width - drawW) / 2;
  const offsetY = (stageSize.height - drawH) / 2;
  const mappedX = offsetX + x * scale;
  return {
    x: props.mirrored ? stageSize.width - mappedX : mappedX,
    y: offsetY + y * scale,
  };
}

function mapBbox() {
  const bbox = normalizedBbox.value;
  const source = props.sourceSize;
  if (!bbox || !source.width || !source.height) return null;
  const [x1, y1, x2, y2] = bbox;
  const p1 = mapPoint(x1, y1);
  const p2 = mapPoint(x2, y2);
  if (!p1 || !p2) return null;
  return {
    x: Math.min(p1.x, p2.x),
    y: Math.min(p1.y, p2.y),
    w: Math.abs(p2.x - p1.x),
    h: Math.abs(p2.y - p1.y),
  };
}

function syncTarget() {
  const mapped = props.enabled && overlayVisible.value ? mapBbox() : null;
  if (!mapped) {
    targetBox.opacity = 0;
    return;
  }
  targetBox.x = mapped.x;
  targetBox.y = mapped.y;
  targetBox.w = mapped.w;
  targetBox.h = mapped.h;
  targetBox.opacity = 1;
}

function resizeCanvas() {
  const root = rootRef.value;
  const canvas = canvasRef.value;
  if (!root || !canvas) return;
  const rect = root.getBoundingClientRect();
  stageSize.width = Math.max(1, rect.width);
  stageSize.height = Math.max(1, rect.height);
  const dpr = window.devicePixelRatio || 1;
  const nextW = Math.round(stageSize.width * dpr);
  const nextH = Math.round(stageSize.height * dpr);
  if (canvas.width !== nextW || canvas.height !== nextH) {
    canvas.width = nextW;
    canvas.height = nextH;
  }
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

function stepBox() {
  const alpha = shouldReduceMotion.value ? 1 : 0.2;
  renderBox.x += (targetBox.x - renderBox.x) * alpha;
  renderBox.y += (targetBox.y - renderBox.y) * alpha;
  renderBox.w += (targetBox.w - renderBox.w) * alpha;
  renderBox.h += (targetBox.h - renderBox.h) * alpha;
  renderBox.opacity += (targetBox.opacity - renderBox.opacity) * alpha;
}

function draw() {
  resizeCanvas();
  syncTarget();
  stepBox();

  const canvas = canvasRef.value;
  const ctx = canvas?.getContext("2d");
  if (!canvas || !ctx) return;
  const dpr = window.devicePixelRatio || 1;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, stageSize.width, stageSize.height);

  if (renderBox.opacity <= 0.01) return;
  const color = decisionMeta.value.color;
  const { x, y, w, h, opacity } = renderBox;
  const pad = Math.max(10, Math.min(w, h) * 0.045);
  const x0 = x - pad;
  const y0 = y - pad;
  const w0 = w + pad * 2;
  const h0 = h + pad * 2;

  ctx.save();
  ctx.globalAlpha = opacity;
  ctx.shadowColor = color;
  ctx.shadowBlur = 18;
  ctx.lineWidth = 2.5;
  ctx.strokeStyle = color;
  roundRectPath(ctx, x0, y0, w0, h0, 18);
  ctx.stroke();

  ctx.shadowBlur = 0;
  ctx.lineWidth = 4;
  ctx.strokeStyle = swuMotionColors.gold;
  const corner = Math.min(36, Math.max(18, Math.min(w0, h0) * 0.16));
  ctx.beginPath();
  ctx.moveTo(x0 + corner, y0); ctx.lineTo(x0, y0); ctx.lineTo(x0, y0 + corner);
  ctx.moveTo(x0 + w0 - corner, y0); ctx.lineTo(x0 + w0, y0); ctx.lineTo(x0 + w0, y0 + corner);
  ctx.moveTo(x0, y0 + h0 - corner); ctx.lineTo(x0, y0 + h0); ctx.lineTo(x0 + corner, y0 + h0);
  ctx.moveTo(x0 + w0 - corner, y0 + h0); ctx.lineTo(x0 + w0, y0 + h0); ctx.lineTo(x0 + w0, y0 + h0 - corner);
  ctx.stroke();

  for (const point of mappedKeypoints.value) {
    ctx.beginPath();
    ctx.fillStyle = "#fff7cc";
    ctx.strokeStyle = color;
    ctx.lineWidth = 2;
    ctx.arc(point.x, point.y, 4.5, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();
  }

  ctx.font = "700 12px 'PingFang SC', 'Microsoft YaHei', sans-serif";
  ctx.fillStyle = "rgba(0, 20, 40, 0.82)";
  roundRectPath(ctx, x0, Math.max(8, y0 - 32), 122, 24, 12);
  ctx.fill();
  ctx.fillStyle = "#ffffff";
  ctx.fillText(`PIPELINE · ${decisionMeta.value.label}`, x0 + 10, Math.max(25, y0 - 15));
  ctx.restore();
}

function animate() {
  draw();
  rafId = window.requestAnimationFrame(animate);
}

onMounted(() => {
  if (!props.showCanvas) return;
  resizeObserver = new ResizeObserver(() => resizeCanvas());
  if (rootRef.value) resizeObserver.observe(rootRef.value);
  animate();
});

onBeforeUnmount(() => {
  if (rafId != null) window.cancelAnimationFrame(rafId);
  resizeObserver?.disconnect();
});
</script>

<template>
  <div ref="rootRef" class="explain-overlay" :class="{ hidden: !overlayVisible && !props.panel, 'is-panel': props.panel }">
    <canvas v-if="props.showCanvas" ref="canvasRef" class="explain-canvas" />

    <button
      v-if="!props.panel && props.showCanvas"
      class="explain-toggle"
      type="button"
      :aria-pressed="overlayVisible"
      @click="overlayVisible = !overlayVisible"
    >
      {{ overlayVisible ? "隐藏解释" : "显示解释" }}
    </button>

    <aside
      v-if="showCard"
      class="explain-card"
      :class="{ danger: isLiveAttack, empty: !normalizedBbox, 'panel-card': props.panel }"
      :style="props.panel ? undefined : cardStyle"
    >
      <div class="card-head">
        <span class="eyebrow">流水线可视化</span>
        <strong :style="{ color: decisionMeta.color }">{{ decisionMeta.text }}</strong>
      </div>

      <div class="identity">
        <span>{{ matchName }}</span>
        <em>阈值 {{ thresholdText }}</em>
      </div>

      <div class="score-grid">
        <div class="score-row">
          <span>检测分</span>
          <strong v-if="detectorPercent != null">
            <span v-if="shouldReduceMotion">{{ detectorPercent.toFixed(1) }}%</span>
            <NumberFlow v-else :value="detectorPercent" :format="percentFormat" suffix="%" locales="zh-CN" />
          </strong>
          <strong v-else class="muted">待检测</strong>
        </div>
        <div class="score-row" :class="{ danger: isLiveAttack }">
          <span>活体分</span>
          <strong v-if="livenessValue != null">
            <span v-if="shouldReduceMotion">{{ livenessValue.toFixed(4) }}</span>
            <NumberFlow v-else :value="livenessValue" :format="probabilityFormat" locales="zh-CN" />
          </strong>
          <strong v-else class="muted">待检测</strong>
        </div>
        <div class="score-row">
          <span>质量分</span>
          <strong v-if="qualityPercent != null">
            <span v-if="shouldReduceMotion">{{ qualityPercent.toFixed(1) }}%</span>
            <NumberFlow v-else :value="qualityPercent" :format="percentFormat" suffix="%" locales="zh-CN" />
          </strong>
          <strong v-else class="muted">待评估</strong>
        </div>
        <div class="score-row">
          <span>Top-1 相似度</span>
          <strong v-if="matchPercent != null">
            <span v-if="shouldReduceMotion">{{ matchPercent.toFixed(1) }}%</span>
            <NumberFlow v-else :value="matchPercent" :format="percentFormat" suffix="%" locales="zh-CN" />
          </strong>
          <strong v-else class="muted">待匹配</strong>
        </div>
      </div>

      <div class="spoof-meter" :class="{ danger: isLiveAttack }">
        <span :style="{ width: `${spoofPercent ?? 0}%` }" />
      </div>

      <p class="footnote">
        关键点：{{ keypointText }} · {{ phaseLabel }}
      </p>
    </aside>
  </div>
</template>

<style scoped>
.explain-overlay {
  position: absolute;
  inset: 0;
  z-index: 5;
  pointer-events: none;
}

.explain-overlay.is-panel {
  position: relative;
  inset: auto;
  z-index: auto;
  display: flex;
  width: 100%;
  height: 100%;
  min-height: 0;
  pointer-events: auto;
}

.explain-canvas {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
}

.explain-toggle {
  position: absolute;
  top: 14px;
  right: 16px;
  z-index: 3;
  pointer-events: auto;
  border: 1px solid rgba(212, 175, 55, 0.42);
  border-radius: 999px;
  padding: 7px 12px;
  color: #fff7cc;
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.05em;
  background: rgba(0, 20, 42, 0.64);
  box-shadow: 0 10px 28px rgba(0, 20, 42, 0.2);
  backdrop-filter: blur(8px);
  cursor: pointer;
}

.explain-card {
  position: absolute;
  left: 0;
  top: 0;
  z-index: 2;
  padding: 12px;
  border: 1px solid rgba(0, 61, 122, 0.72);
  border-radius: 16px;
  color: #fff;
  background:
    linear-gradient(145deg, rgba(0, 20, 42, 0.9), rgba(0, 61, 122, 0.74)),
    radial-gradient(circle at 10% 0%, rgba(212, 175, 55, 0.18), transparent 38%);
  box-shadow: 0 18px 42px rgba(0, 18, 38, 0.34);
  backdrop-filter: blur(12px);
  transition: opacity 0.18s ease;
}

.explain-card.panel-card {
  position: relative;
  left: auto;
  top: auto;
  display: flex;
  flex-direction: column;
  width: 100%;
  min-height: 100%;
  padding: 20px;
  border-color: rgba(0, 61, 122, 0.34);
  border-radius: 26px;
  background:
    radial-gradient(circle at 88% 0%, rgba(212, 175, 55, 0.2), transparent 32%),
    linear-gradient(155deg, rgba(4, 17, 31, 0.96), rgba(0, 61, 122, 0.82) 58%, rgba(3, 10, 20, 0.94));
  box-shadow:
    0 24px 70px rgba(0, 35, 76, 0.2),
    inset 0 1px 0 rgba(255, 255, 255, 0.08);
}

.hidden .explain-card,
.hidden .explain-canvas {
  opacity: 0;
}

.explain-card.danger {
  background:
    linear-gradient(145deg, rgba(49, 8, 14, 0.92), rgba(178, 34, 34, 0.7)),
    radial-gradient(circle at 10% 0%, rgba(212, 175, 55, 0.18), transparent 38%);
}

.explain-card.panel-card.danger {
  background:
    radial-gradient(circle at 88% 0%, rgba(212, 175, 55, 0.2), transparent 32%),
    linear-gradient(155deg, rgba(49, 8, 14, 0.96), rgba(178, 34, 34, 0.74) 58%, rgba(30, 6, 10, 0.94));
}

.card-head,
.identity,
.score-row,
.footnote {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.card-head strong {
  font-size: 18px;
}

.eyebrow,
.identity em,
.footnote {
  color: rgba(255, 255, 255, 0.62);
  font-size: 11px;
  font-style: normal;
  letter-spacing: 0.06em;
}

.identity {
  margin-top: 8px;
  padding-bottom: 10px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.12);
}

.identity span {
  overflow: hidden;
  max-width: 138px;
  font-size: 13px;
  font-weight: 800;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.panel-card .identity span {
  max-width: none;
  font-size: 15px;
}

.score-grid {
  display: grid;
  gap: 8px;
  margin-top: 10px;
}

.panel-card .score-grid {
  gap: 12px;
  margin-top: 18px;
}

.panel-card .score-row {
  padding: 12px 14px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.075);
}

.score-row span {
  color: rgba(255, 255, 255, 0.7);
  font-size: 12px;
}

.score-row strong {
  font-size: 13px;
  font-variant-numeric: tabular-nums;
}

.panel-card .score-row strong {
  font-size: 20px;
  line-height: 1;
}

.score-row.danger strong {
  color: #ffd3d3;
}

.muted {
  color: rgba(255, 255, 255, 0.48);
  font-weight: 700;
}

.spoof-meter {
  height: 6px;
  margin-top: 10px;
  overflow: hidden;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.14);
}

.panel-card .spoof-meter {
  height: 9px;
  margin-top: 18px;
}

.spoof-meter span {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #b22222, #d4af37, #20c36b);
}

.spoof-meter.danger span {
  background: linear-gradient(90deg, #b22222, #ef4444);
}

.footnote {
  margin: 9px 0 0;
}

.panel-card .footnote {
  margin-top: 14px;
  padding-top: 14px;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
  font-size: 12px;
}

@media (max-width: 680px) {
  .explain-overlay:not(.is-panel) .explain-card {
    display: none;
  }

  .explain-toggle {
    top: 56px;
    right: 12px;
    padding: 6px 10px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .explain-card {
    transition: none;
  }
}
</style>
