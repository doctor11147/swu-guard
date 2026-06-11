<!-- 视觉参考: skills/art-design-pro 的 shadow-mode 卡片层级 + 现有西小卫首页品牌色。 -->
<script setup lang="ts">
import type { GateOut } from "@/api/types";
import {
  bindGateMarkers,
  gateStatusClass,
  gateStatusLabel,
  listUnmarkedGates,
  MAP_H,
  MAP_W,
  MARKERS,
  type BoundGateMarker,
} from "./gateMarkers";
import { gateFocusKey, useGateFocus } from "./useGateFocus";

const props = defineProps<{
  gates: GateOut[];
}>();

const router = useRouter();
const gateFocus = inject(gateFocusKey, undefined) ?? useGateFocus();
const { activeGateNo, focusGate, scheduleHide, clearHide } = gateFocus;
const canHover = ref(true);

const markers = computed(() => bindGateMarkers(props.gates));
const unmarkedGates = computed(() => listUnmarkedGates(props.gates));
const activeMarker = computed(() =>
  markers.value.find((marker) => marker.gateNo === activeGateNo.value) ?? null,
);

function toggleMarker(marker: BoundGateMarker) {
  clearHide();
  activeGateNo.value = activeGateNo.value === marker.gateNo ? null : marker.gateNo;
}

function clickMarker(marker: BoundGateMarker) {
  if (canHover.value && marker.gate) {
    enterGate(marker);
    return;
  }
  toggleMarker(marker);
}

function enterGate(marker: BoundGateMarker) {
  if (!marker.gate) return;
  router.push(`/gates/${marker.gate.id}/recognize`);
}

function onMarkerKeydown(event: KeyboardEvent, marker: BoundGateMarker) {
  if (event.key !== "Enter" && event.key !== " ") return;
  event.preventDefault();
  enterGate(marker);
}

function markerLabel(marker: BoundGateMarker) {
  const name = marker.gate?.name || `第 ${marker.gateNo} 校门`;
  return `${name}，状态${gateStatusLabel(marker.gate?.status)}`;
}

function cardSide(marker: BoundGateMarker) {
  const x = marker.cx / MAP_W;
  const y = marker.cy / MAP_H;
  if (y < 0.2) return "bottom";
  if (y > 0.78) return "top";
  if (x < 0.16) return "right";
  if (x > 0.82) return "left";
  return "top";
}

function cardStyle(marker: BoundGateMarker) {
  const x = marker.cx / MAP_W;
  const cardX = x > 0.62 ? "-82%" : x < 0.38 ? "-18%" : "-50%";
  return {
    left: `${(marker.cx / MAP_W) * 100}%`,
    top: `${(marker.cy / MAP_H) * 100}%`,
    "--card-x": cardX,
  };
}

function cardTitle(marker: BoundGateMarker) {
  return marker.gate?.name || `第 ${marker.gateNo} 校门`;
}

function preloadImages() {
  const run = () => {
    for (const marker of MARKERS) {
      const image = new Image();
      image.src = marker.image;
    }
  };
  const idle = window.requestIdleCallback;
  if (idle) idle(run);
  else window.setTimeout(run, 300);
}

onMounted(preloadImages);

onMounted(() => {
  canHover.value = window.matchMedia("(hover: hover) and (pointer: fine)").matches;
});

</script>

<template>
  <div class="campus-map">
    <div
      class="map-wrap"
      @click="activeGateNo = null"
    >
      <h2 class="map-title">西南大学校园地图</h2>

      <img
        class="map-img"
        src="/gates/campus-map.png"
        alt="西南大学校园门禁地图"
        draggable="false"
      />

      <svg
        class="map-overlay"
        :viewBox="`0 0 ${MAP_W} ${MAP_H}`"
        preserveAspectRatio="xMidYMid meet"
        aria-label="校园门禁地图标记"
      >
        <g
          v-for="marker in markers"
          :key="marker.gateNo"
          :class="['marker-group', activeGateNo === marker.gateNo && 'is-active', !marker.gate && 'is-unbound']"
          role="button"
          tabindex="0"
          :aria-label="markerLabel(marker)"
          @mouseenter="focusGate(marker.gateNo)"
          @mouseleave="scheduleHide"
          @focus="focusGate(marker.gateNo)"
          @blur="scheduleHide"
          @click.stop="clickMarker(marker)"
          @keydown="onMarkerKeydown($event, marker)"
        >
          <circle
            class="marker-hotspot"
            :cx="marker.cx"
            :cy="marker.cy"
            :r="marker.r * 1.3"
          />
          <circle
            v-if="marker.gate"
            class="marker-pulse"
            :cx="marker.cx"
            :cy="marker.cy"
            :r="marker.r * 0.58"
          />
          <circle
            class="marker-dot"
            :cx="marker.cx"
            :cy="marker.cy"
            :r="marker.r * 0.24"
          />
          <circle
            class="marker-ring"
            :cx="marker.cx"
            :cy="marker.cy"
            :r="marker.r * 0.42"
          />
          <text
            class="marker-text"
            :x="marker.cx"
            :y="marker.cy + marker.r + 18"
            text-anchor="middle"
          >
            {{ marker.gateNo }}
          </text>
        </g>
      </svg>

      <transition name="card-pop">
        <article
          v-if="activeMarker"
          :key="activeMarker.gateNo"
          :class="['gate-float-card', `side-${cardSide(activeMarker)}`, !activeMarker.gate && 'is-unbound']"
          :style="cardStyle(activeMarker)"
          @mouseenter="clearHide"
          @mouseleave="scheduleHide"
          @click.stop
        >
          <span class="hover-bridge" aria-hidden="true" />
          <div class="gate-image-wrap">
            <img
              class="gate-image"
              :src="activeMarker.image"
              :alt="`${cardTitle(activeMarker)}实景图`"
            />
          </div>
          <div class="card-body">
            <div class="card-head">
              <div>
                <h3>{{ cardTitle(activeMarker) }}</h3>
                <p>{{ activeMarker.gate?.location || "该门暂未在系统登记" }}</p>
              </div>
              <span :class="['status-badge', gateStatusClass(activeMarker.gate?.status)]">
                {{ gateStatusLabel(activeMarker.gate?.status) }}
              </span>
            </div>
            <button
              type="button"
              class="enter-btn"
              :disabled="!activeMarker.gate"
              @click="enterGate(activeMarker)"
            >
              点击进入
            </button>
          </div>
        </article>
      </transition>
    </div>

    <p v-if="unmarkedGates.length" class="unmarked-note">
      未在地图标注的门:
      <span v-for="gate in unmarkedGates" :key="gate.id">{{ gate.name }}</span>
    </p>
  </div>
</template>

<style scoped>
.campus-map {
  width: 100%;
}

.map-wrap {
  position: relative;
  width: 100%;
  margin: 0;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.72);
  box-shadow:
    0 18px 42px rgba(27, 79, 142, 0.12),
    0 3px 10px rgba(0, 0, 0, 0.06);
  overflow: visible;
}

.map-title {
  position: absolute;
  top: clamp(22px, 3.2vw, 42px);
  left: clamp(26px, 4vw, 56px);
  z-index: 3;
  margin: 0;
  color: #172033;
  font-size: clamp(22px, 2.4vw, 34px);
  font-weight: 900;
  line-height: 1.15;
  letter-spacing: 0.04em;
  text-shadow: 0 8px 24px rgba(27, 79, 142, 0.12);
  pointer-events: none;
}

.map-img {
  display: block;
  width: 100%;
  height: auto;
  border-radius: 18px;
  user-select: none;
}

.map-overlay {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  overflow: visible;
  pointer-events: none;
}

.marker-group {
  color: var(--xw-primary, #003d7a);
  outline: none;
  cursor: pointer;
  pointer-events: auto;
}

.marker-group.is-unbound {
  color: #7b8794;
  cursor: default;
}

.marker-hotspot {
  fill: transparent;
  pointer-events: all;
}

.marker-pulse {
  fill: currentColor;
  opacity: 0.22;
  transform-box: fill-box;
  transform-origin: center;
  animation: markerPulse 1.6s ease-out infinite;
}

.marker-dot {
  fill: currentColor;
  stroke: #fff;
  stroke-width: 5;
  filter: drop-shadow(0 4px 8px rgba(0, 61, 122, 0.28));
}

.marker-ring {
  fill: transparent;
  stroke: currentColor;
  stroke-width: 4;
  opacity: 0.9;
}

.marker-text {
  fill: #fff;
  paint-order: stroke;
  stroke: rgba(23, 32, 51, 0.72);
  stroke-width: 4;
  font-size: 38px;
  font-weight: 800;
  letter-spacing: 0;
  pointer-events: none;
}

.marker-group:focus-visible .marker-ring,
.marker-group:hover .marker-ring,
.marker-group.is-active .marker-ring {
  stroke-width: 6;
}

.marker-group.is-active .marker-dot {
  filter:
    drop-shadow(0 6px 12px rgba(0, 61, 122, 0.38))
    drop-shadow(0 0 10px rgba(212, 175, 55, 0.72));
}

.gate-float-card {
  position: absolute;
  z-index: 5;
  width: min(320px, 34vw);
  min-width: 260px;
  border: 1px solid rgba(27, 79, 142, 0.1);
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.96);
  box-shadow:
    0 22px 40px rgba(23, 32, 51, 0.18),
    0 4px 12px rgba(27, 79, 142, 0.12);
  overflow: visible;
}

.gate-float-card.side-top {
  transform: translate(var(--card-x), calc(-100% - 16px));
}

.gate-float-card.side-bottom {
  transform: translate(var(--card-x), 16px);
}

.gate-float-card.side-left {
  transform: translate(calc(-100% - 16px), -50%);
}

.gate-float-card.side-right {
  transform: translate(16px, -50%);
}

.hover-bridge {
  position: absolute;
  z-index: 0;
  display: block;
  background: transparent;
  pointer-events: auto;
}

.gate-image-wrap,
.card-body {
  position: relative;
  z-index: 1;
}

.side-top .hover-bridge {
  left: 30%;
  right: 30%;
  bottom: -20px;
  height: 24px;
}

.side-bottom .hover-bridge {
  left: 30%;
  right: 30%;
  top: -20px;
  height: 24px;
}

.side-left .hover-bridge {
  top: 20%;
  bottom: 20%;
  right: -20px;
  width: 24px;
}

.side-right .hover-bridge {
  top: 20%;
  bottom: 20%;
  left: -20px;
  width: 24px;
}

.gate-image-wrap {
  padding: 10px 10px 0;
}

.gate-image {
  display: block;
  width: 100%;
  aspect-ratio: 16 / 10;
  object-fit: cover;
  border-radius: 12px;
  background: #e7edf5;
}

.card-body {
  padding: 12px 14px 14px;
}

.card-head {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 10px;
  align-items: start;
}

.card-head h3 {
  margin: 0;
  color: var(--xw-text, #172033);
  font-size: 16px;
  line-height: 1.25;
  letter-spacing: 0;
}

.card-head p {
  margin: 5px 0 0;
  color: var(--xw-muted, #637083);
  font-size: 12px;
  line-height: 1.45;
}

.status-badge {
  min-width: 46px;
  padding: 4px 8px;
  border-radius: 999px;
  text-align: center;
  font-size: 12px;
  font-weight: 700;
  white-space: nowrap;
}

.status-badge.is-active {
  color: #0f7a42;
  background: #dff7eb;
}

.status-badge.is-maintenance {
  color: #9a5b00;
  background: #fff2cc;
}

.status-badge.is-disabled {
  color: #667085;
  background: #eef2f6;
}

.enter-btn {
  width: 100%;
  min-height: 38px;
  margin-top: 12px;
  border: 0;
  border-radius: 12px;
  color: #fff;
  background: linear-gradient(135deg, var(--xw-primary, #003d7a), #2b6cb0);
  font-weight: 700;
  cursor: pointer;
  box-shadow: 0 8px 18px rgba(27, 79, 142, 0.22);
  transition: transform 0.18s ease, box-shadow 0.18s ease;
}

.enter-btn:hover {
  transform: translateY(-1px);
  box-shadow: 0 12px 24px rgba(27, 79, 142, 0.28);
}

.enter-btn:disabled {
  color: #98a2b3;
  background: #edf1f5;
  box-shadow: none;
  cursor: not-allowed;
  transform: none;
}

.unmarked-note {
  width: 100%;
  margin: 12px 0 0;
  color: var(--xw-muted, #637083);
  font-size: 13px;
}

.unmarked-note span + span::before {
  content: "、";
}

.card-pop-enter-active,
.card-pop-leave-active {
  transition: opacity 0.16s ease, scale 0.16s ease;
}

.card-pop-enter-from,
.card-pop-leave-to {
  opacity: 0;
  scale: 0.96;
}

@keyframes markerPulse {
  0% {
    opacity: 0.34;
    scale: 0.65;
  }
  100% {
    opacity: 0;
    scale: 2.1;
  }
}

@media (max-width: 900px) {
  .gate-float-card {
    width: min(280px, 76vw);
    min-width: 220px;
  }

  .marker-text {
    font-size: 44px;
  }
}

@media (max-width: 520px) {
  .map-wrap {
    border-radius: 14px;
  }

  .map-img {
    border-radius: 14px;
  }

  .gate-float-card {
    width: min(250px, 82vw);
  }

  .card-head {
    grid-template-columns: 1fr;
  }
}
</style>
