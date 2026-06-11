<script setup lang="ts">
import { usePreferredReducedMotion } from "@vueuse/core";
import { gsap } from "gsap";
import { computed, nextTick, onBeforeUnmount, ref, watch } from "vue";

import type { PublicRecognizeDecision } from "@/api/types";
import { motionDurations, motionEase } from "@/styles/motion-tokens";
import SuccessCheck from "./animations/SuccessCheck.vue";
import DeniedCross from "./animations/DeniedCross.vue";
import SpoofWarning from "./animations/SpoofWarning.vue";
import NetworkError from "./animations/NetworkError.vue";

const props = defineProps<{
  decision: PublicRecognizeDecision;
  name?: string;
  spoof?: boolean;
}>();

const emit = defineEmits<{ (e: "done"): void }>();

const visible = ref(false);
const cardRef = ref<HTMLElement>();
const reducedMotion = usePreferredReducedMotion();
let hideTimer: number | null = null;
let tween: gsap.core.Tween | null = null;

const stopped = computed(() => props.decision === "network");
const tone = computed(() => props.decision === "granted"
  ? "granted"
  : props.decision === "spoof"
    ? "spoof"
    : props.decision === "network"
      ? "network"
      : "denied");

function clearHideTimer() {
  if (hideTimer != null) window.clearTimeout(hideTimer);
  hideTimer = null;
}

function playEntrance() {
  tween?.kill();
  if (!cardRef.value || reducedMotion.value === "reduce") return;
  tween = gsap.fromTo(cardRef.value,
    { y: 34, scale: 0.92, opacity: 0, filter: "blur(10px)" },
    { y: 0, scale: 1, opacity: 1, filter: "blur(0px)", duration: motionDurations.slow, ease: motionEase.entrance },
  );
}

watch(() => props.decision, async () => {
  clearHideTimer();
  visible.value = true;
  await nextTick();
  playEntrance();
  const dur = props.spoof ? 3000 : 2500;
  hideTimer = window.setTimeout(() => {
    visible.value = false;
    emit("done");
  }, dur);
}, { immediate: true });

onBeforeUnmount(() => {
  clearHideTimer();
  tween?.kill();
});
</script>

<template>
  <Transition name="fade">
    <div v-if="visible" class="overlay" :class="`is-${tone}`" role="status" aria-live="polite">
      <div ref="cardRef" class="result-card">
        <SuccessCheck v-if="decision === 'granted'" :name="name" />
        <DeniedCross v-else-if="decision === 'denied' || decision === 'no_match'" />
        <SpoofWarning v-else-if="decision === 'spoof'" />
        <NetworkError v-else :stopped="stopped" />
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.overlay {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background:
    radial-gradient(circle at 50% 42%, rgba(255,255,255,0.16), transparent 28%),
    rgba(1, 12, 25, 0.72);
  backdrop-filter: blur(12px);
}
.result-card {
  position: relative;
  width: min(420px, calc(100vw - 44px));
  min-height: 330px;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px 32px;
  border: 1px solid rgba(255,255,255,0.18);
  border-radius: 34px;
  background:
    linear-gradient(145deg, rgba(4, 17, 31, 0.92), rgba(10, 35, 64, 0.84)),
    rgba(255,255,255,0.08);
  box-shadow:
    0 30px 100px rgba(0, 0, 0, 0.42),
    inset 0 0 0 1px rgba(255,255,255,0.06);
  overflow: hidden;
}
.result-card::before {
  content: "";
  position: absolute;
  inset: -45%;
  opacity: 0.42;
  background: conic-gradient(from 120deg, transparent, rgba(212,175,55,0.34), transparent 38%);
  animation: halo 4s linear infinite;
}
.result-card > :deep(*) {
  position: relative;
  z-index: 1;
}
.is-granted .result-card { border-color: rgba(32,195,107,0.38); }
.is-denied .result-card { border-color: rgba(249,115,22,0.38); }
.is-spoof .result-card { border-color: rgba(239,68,68,0.44); }
.is-network .result-card { border-color: rgba(148,163,184,0.36); }
@keyframes halo { to { transform: rotate(360deg); } }
.fade-enter-active, .fade-leave-active { transition: opacity 0.32s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
@media (prefers-reduced-motion: reduce) {
  .result-card::before { animation: none; }
  .fade-enter-active, .fade-leave-active { transition: opacity 0.12s ease; }
}
</style>
