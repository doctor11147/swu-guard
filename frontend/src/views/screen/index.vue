<script setup lang="ts">
/**
 * 数据大屏装配层：数据、缩放、全屏与进场编排在此收口，图表和动效细节下沉到私有组件。
 */
import { FullScreen } from "@element-plus/icons-vue";
import { usePreferredReducedMotion } from "@vueuse/core";
import gsap from "gsap";
import { computed, nextTick, onActivated, onBeforeUnmount, onDeactivated, onMounted, ref } from "vue";

import { motionDurations, motionEase } from "@/styles/motion-tokens";

import DecisionPie from "./components/DecisionPie.vue";
import GateMapPanel from "./components/GateMapPanel.vue";
import KpiCard from "./components/KpiCard.vue";
import LiveFeed from "./components/LiveFeed.vue";
import RankBoard from "./components/RankBoard.vue";
import ScreenHeader from "./components/ScreenHeader.vue";
import ScreenPanel from "./components/ScreenPanel.vue";
import TrendChart from "./components/TrendChart.vue";
import { useScreenData } from "./composables/useScreenData";
import { useScreenScale } from "./composables/useScreenScale";

const {
  dashboard,
  gates,
  loading,
  error,
  clockText,
  lastUpdatedText,
  gateStats,
  kpiCards,
  trendRows,
  rankRows,
  decisionRows,
  recentLogs,
  decisionLabel,
} = useScreenData();

const { screenStyle } = useScreenScale();
const reducedMotion = usePreferredReducedMotion();
const viewportRef = ref<HTMLElement | null>(null);
const screenRef = ref<HTMLElement | null>(null);
const isFullscreen = ref(false);
let entranceCtx: gsap.Context | null = null;

interface WebkitDocument extends Document {
  webkitFullscreenElement?: Element | null;
  webkitExitFullscreen?: () => Promise<void> | void;
}

interface WebkitHTMLElement extends HTMLElement {
  webkitRequestFullscreen?: () => Promise<void> | void;
}

const schoolName = computed(() => dashboard.value.school.name_zh || "西南大学");
const statusText = computed(() => {
  if (error.value) return "数据链路重试中";
  if (loading.value) return "数据刷新中";
  return "实时在线";
});

const miniStats = computed(() => [
  { label: "注册人员", value: dashboard.value.persons_total.toLocaleString("zh-CN"), tone: "cyan" },
  { label: "激活人员", value: dashboard.value.persons_active.toLocaleString("zh-CN"), tone: "green" },
  { label: "人脸向量", value: dashboard.value.embedding_total.toLocaleString("zh-CN"), tone: "gold" },
  { label: "本周通行", value: dashboard.value.week.total.toLocaleString("zh-CN"), tone: "blue" },
]);

function fullscreenElement() {
  const doc = document as WebkitDocument;
  return document.fullscreenElement || doc.webkitFullscreenElement || null;
}

function syncFullscreenState() {
  isFullscreen.value = Boolean(fullscreenElement());
}

async function requestFullscreen(target: HTMLElement) {
  const el = target as WebkitHTMLElement;
  if (el.requestFullscreen) await el.requestFullscreen();
  else await el.webkitRequestFullscreen?.();
}

async function exitFullscreen() {
  const doc = document as WebkitDocument;
  if (document.exitFullscreen) await document.exitFullscreen();
  else await doc.webkitExitFullscreen?.();
}

async function toggleFullscreen() {
  if (fullscreenElement()) {
    await exitFullscreen();
  } else if (viewportRef.value) {
    await requestFullscreen(viewportRef.value);
  }
  syncFullscreenState();
}

async function runEntranceMotion() {
  entranceCtx?.revert();
  entranceCtx = null;
  await nextTick();
  if (reducedMotion.value === "reduce" || !screenRef.value) return;

  entranceCtx = gsap.context(() => {
    gsap.from(".screen-reveal", {
      opacity: 0,
      y: 30,
      duration: motionDurations.slow,
      ease: motionEase.standard,
      stagger: 0.055,
    });
    gsap.to(".screen-viewport__sweep", {
      xPercent: 120,
      duration: 9,
      repeat: -1,
      ease: "none",
    });
  }, screenRef.value);
}

function cleanupEntranceMotion() {
  entranceCtx?.revert();
  entranceCtx = null;
}

onMounted(() => {
  document.addEventListener("fullscreenchange", syncFullscreenState);
  document.addEventListener("webkitfullscreenchange", syncFullscreenState);
  void runEntranceMotion();
});

onActivated(() => void runEntranceMotion());
onDeactivated(cleanupEntranceMotion);

onBeforeUnmount(() => {
  cleanupEntranceMotion();
  document.removeEventListener("fullscreenchange", syncFullscreenState);
  document.removeEventListener("webkitfullscreenchange", syncFullscreenState);
  if (fullscreenElement()) void exitFullscreen();
});
</script>

<template>
  <div ref="viewportRef" class="screen-viewport">
    <div class="screen-viewport__aura" />
    <div class="screen-viewport__sweep" />

    <main ref="screenRef" class="screen-canvas" :style="screenStyle">
      <ScreenHeader
        class="screen-reveal"
        :clock-text="clockText"
        :school-name="schoolName"
        :gates-online="gateStats.online"
        :gates-total="gateStats.total"
        :last-updated="lastUpdatedText"
      />

      <section class="screen-kpis" aria-label="核心指标">
        <KpiCard
          v-for="card in kpiCards"
          :key="card.key"
          class="screen-reveal"
          :title="card.title"
          :value="card.value"
          :suffix="card.suffix"
          :subtitle="card.subtitle"
          :tone="card.tone"
          :icon="card.icon"
          :decimals="card.decimals ?? 0"
        />
      </section>

      <section class="screen-grid" aria-label="可视化分析区">
        <div class="screen-col screen-col--left">
          <ScreenPanel class="screen-reveal" title="北碚门禁态势地图" variant="accent">
            <template #meta>{{ gates.length }} 个节点</template>
            <GateMapPanel :gates="gates" />
          </ScreenPanel>

          <ScreenPanel class="screen-reveal" title="学部通行排行">
            <template #meta>DataV ScrollBoard</template>
            <RankBoard :rows="rankRows" />
          </ScreenPanel>
        </div>

        <div class="screen-col screen-col--center">
          <ScreenPanel class="screen-reveal" title="24 小时通行趋势">
            <template #meta>{{ statusText }}</template>
            <TrendChart :rows="trendRows" />
          </ScreenPanel>

          <ScreenPanel class="screen-reveal" title="人员与算法底座" variant="primary">
            <template #meta>Vector Registry</template>
            <div class="mini-stats">
              <div v-for="item in miniStats" :key="item.label" :class="['mini-stat', `mini-stat--${item.tone}`]">
                <span class="mini-stat__label">{{ item.label }}</span>
                <strong class="mini-stat__value">{{ item.value }}</strong>
              </div>
            </div>
            <div class="system-line">
              <span>SCRFD 检测</span>
              <i />
              <span>EdgeFace 特征</span>
              <i />
              <span>Silent-FAS 活体</span>
              <i />
              <span>FAISS 1:N 检索</span>
            </div>
          </ScreenPanel>
        </div>

        <div class="screen-col screen-col--right">
          <ScreenPanel class="screen-reveal" title="今日决策分布" variant="danger">
            <template #meta>granted / rejected / spoof</template>
            <DecisionPie :rows="decisionRows" />
          </ScreenPanel>

          <ScreenPanel class="screen-reveal" title="实时通行事件" variant="accent">
            <template #meta>AutoAnimate</template>
            <LiveFeed :logs="recentLogs" :labels="decisionLabel" />
          </ScreenPanel>
        </div>
      </section>

      <button type="button" class="screen-fullscreen" :aria-pressed="isFullscreen" @click="toggleFullscreen">
        <el-icon><FullScreen /></el-icon>
        <span>{{ isFullscreen ? '退出全屏' : '全屏' }}</span>
      </button>

      <div v-if="error" class="screen-toast" role="status">
        数据暂不可用，正在等待下一次刷新
      </div>
    </main>
  </div>
</template>

<style scoped>
.screen-viewport {
  position: fixed;
  inset: 0;
  overflow: hidden;
  background:
    radial-gradient(circle at 18% 18%, rgba(39, 216, 255, 0.17), transparent 28%),
    radial-gradient(circle at 80% 78%, rgba(212, 175, 55, 0.11), transparent 26%),
    linear-gradient(135deg, #00142b 0%, #001b3d 48%, #020a18 100%);
  color: #eaf4ff;
  font-family: "PingFang SC", "Microsoft YaHei", "DIN Alternate", sans-serif;
}

.screen-viewport::before {
  content: "";
  position: absolute;
  inset: 0;
  opacity: 0.26;
  background-image:
    linear-gradient(rgba(39, 216, 255, 0.08) 1px, transparent 1px),
    linear-gradient(90deg, rgba(39, 216, 255, 0.08) 1px, transparent 1px);
  background-size: 44px 44px;
  mask-image: radial-gradient(circle at center, black, transparent 74%);
}

.screen-viewport__aura {
  position: absolute;
  inset: -16% -10%;
  background:
    conic-gradient(from 220deg at 50% 50%, transparent 0deg, rgba(39, 216, 255, 0.1) 80deg, transparent 150deg, rgba(212, 175, 55, 0.08) 240deg, transparent 360deg);
  filter: blur(10px);
  opacity: 0.9;
}

.screen-viewport__sweep {
  position: absolute;
  top: 0;
  bottom: 0;
  left: -30%;
  width: 28%;
  pointer-events: none;
  background: linear-gradient(90deg, transparent, rgba(39, 216, 255, 0.08), transparent);
  transform: skewX(-18deg);
}

.screen-canvas {
  position: absolute;
  top: 0;
  left: 0;
  display: flex;
  transform-origin: 0 0;
  flex-direction: column;
  gap: 18px;
  padding: 26px 30px 28px;
  overflow: hidden;
}

.screen-kpis {
  display: grid;
  height: 150px;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 18px;
}

.screen-grid {
  display: grid;
  flex: 1;
  min-height: 0;
  grid-template-columns: 510px minmax(0, 1fr) 510px;
  gap: 18px;
}

.screen-col {
  display: grid;
  min-height: 0;
  gap: 18px;
}

.screen-col--left {
  grid-template-rows: minmax(0, 1.32fr) minmax(0, 1fr);
}

.screen-col--center {
  grid-template-rows: minmax(0, 1.42fr) minmax(0, 0.86fr);
}

.screen-col--right {
  grid-template-rows: minmax(0, 0.94fr) minmax(0, 1.34fr);
}

.mini-stats {
  display: grid;
  height: calc(100% - 58px);
  min-height: 0;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
}

.mini-stat {
  position: relative;
  display: flex;
  flex-direction: column;
  justify-content: center;
  overflow: hidden;
  padding: 18px 16px;
  border: 1px solid rgba(39, 216, 255, 0.14);
  border-radius: 16px;
  background: linear-gradient(180deg, rgba(39, 216, 255, 0.08), rgba(0, 61, 122, 0.12));
}

.mini-stat::after {
  content: "";
  position: absolute;
  right: -22px;
  bottom: -22px;
  width: 86px;
  height: 86px;
  border-radius: 999px;
  background: currentColor;
  filter: blur(28px);
  opacity: 0.18;
}

.mini-stat__label {
  color: #8aa8c7;
  font-size: 14px;
  letter-spacing: 0.12em;
}

.mini-stat__value {
  margin-top: 12px;
  color: #eaf4ff;
  font-family: Impact, "DIN Alternate", sans-serif;
  font-size: 42px;
  letter-spacing: 0.04em;
}

.mini-stat--cyan { color: #27d8ff; }
.mini-stat--green { color: #20c36b; }
.mini-stat--gold { color: #d4af37; }
.mini-stat--blue { color: #4ba3ff; }

.system-line {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 13px;
  margin-top: 18px;
  color: #8aa8c7;
  font-size: 13px;
  letter-spacing: 0.12em;
}

.system-line i {
  width: 32px;
  height: 1px;
  background: linear-gradient(90deg, transparent, #27d8ff, transparent);
}

.screen-fullscreen {
  position: absolute;
  right: 34px;
  bottom: 30px;
  z-index: 20;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  height: 42px;
  padding: 0 18px;
  border: 1px solid rgba(39, 216, 255, 0.36);
  border-radius: 999px;
  background: rgba(0, 20, 43, 0.72);
  color: #27d8ff;
  cursor: pointer;
  font-size: 14px;
  font-weight: 800;
  letter-spacing: 0.12em;
  box-shadow: 0 0 22px rgba(39, 216, 255, 0.12);
}

.screen-fullscreen:hover {
  border-color: #d4af37;
  color: #d4af37;
  box-shadow: 0 0 28px rgba(212, 175, 55, 0.18);
}

.screen-toast {
  position: absolute;
  left: 50%;
  bottom: 30px;
  z-index: 19;
  transform: translateX(-50%);
  padding: 10px 18px;
  border: 1px solid rgba(178, 34, 34, 0.4);
  border-radius: 999px;
  background: rgba(178, 34, 34, 0.14);
  color: #ffb4b4;
  font-size: 13px;
  letter-spacing: 0.1em;
}

@media (prefers-reduced-motion: reduce) {
  .screen-viewport__sweep,
  .screen-viewport__aura {
    display: none;
  }

  .screen-fullscreen {
    transition: none;
  }
}
</style>
