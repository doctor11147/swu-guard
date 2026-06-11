<script setup lang="ts">
import { usePreferredReducedMotion } from "@vueuse/core";
import gsap from "gsap";
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";

import { motionDurations, motionEase } from "@/styles/motion-tokens";

import KpiNumber from "./KpiNumber.vue";
import ScreenPanel from "./ScreenPanel.vue";

type KpiTone = "primary" | "success" | "danger" | "gold";

const props = withDefaults(defineProps<{
  title: string;
  value: number;
  suffix?: string;
  subtitle?: string;
  tone?: KpiTone;
  icon?: string;
  decimals?: number;
}>(), {
  suffix: "",
  subtitle: "",
  tone: "primary",
  icon: "AI",
  decimals: 0,
});

const rootRef = ref<HTMLElement | null>(null);
const motion = usePreferredReducedMotion();
let ctx: gsap.Context | null = null;

const panelVariant = computed(() => (props.tone === "danger" ? "danger" : props.tone === "gold" ? "accent" : "compact"));
const canPulse = computed(() => motion.value !== "reduce" && (props.tone === "danger" || props.tone === "gold"));

onMounted(() => {
  if (rootRef.value) ctx = gsap.context(() => {}, rootRef.value);
});

watch(
  () => props.value,
  (value, oldValue) => {
    if (oldValue === undefined || value === oldValue || !rootRef.value || !canPulse.value) return;
    ctx?.add(() => {
      const halo = rootRef.value?.querySelector(".kpi-card__halo") as HTMLElement | null;
      if (!halo) return;
      gsap.fromTo(
        halo,
        { opacity: 0.9, scale: 0.92 },
        { opacity: 0, scale: 1.12, duration: motionDurations.slow, ease: motionEase.standard },
      );
    });
  },
);

onBeforeUnmount(() => {
  ctx?.revert();
  ctx = null;
});
</script>

<template>
  <div ref="rootRef" :class="['kpi-card', `kpi-card--${tone}`]">
    <ScreenPanel :variant="panelVariant" height="100%" :padded="false">
      <div class="kpi-card__content">
        <div class="kpi-card__halo" />
        <div class="kpi-card__topline">
          <span class="kpi-card__icon">{{ icon }}</span>
          <span class="kpi-card__title">{{ title }}</span>
        </div>
        <div class="kpi-card__value">
          <KpiNumber :value="value" :suffix="suffix" :decimals="decimals" />
        </div>
        <div class="kpi-card__subtitle">{{ subtitle }}</div>
      </div>
    </ScreenPanel>
  </div>
</template>

<style scoped>
.kpi-card {
  position: relative;
  height: 150px;
  min-width: 0;
}

.kpi-card__content {
  position: relative;
  display: flex;
  height: 100%;
  min-height: 0;
  flex-direction: column;
  justify-content: center;
  padding: 22px 24px 18px;
  overflow: hidden;
}

.kpi-card__halo {
  position: absolute;
  inset: 10px;
  border-radius: 16px;
  opacity: 0;
  pointer-events: none;
  background: radial-gradient(circle at 50% 50%, rgba(212, 175, 55, 0.42), transparent 62%);
}

.kpi-card__topline {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  color: #8aa8c7;
  font-size: 15px;
  letter-spacing: 0.1em;
}

.kpi-card__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 48px;
  height: 24px;
  border-radius: 999px;
  border: 1px solid rgba(39, 216, 255, 0.24);
  background: rgba(39, 216, 255, 0.08);
  color: #27d8ff;
  font-size: 11px;
  font-weight: 800;
}

.kpi-card__title {
  flex: 1;
  min-width: 0;
  text-align: right;
}

.kpi-card__value {
  margin-top: 10px;
  color: #eaf4ff;
  font-family: Impact, "Arial Narrow", "DIN Alternate", sans-serif;
  font-size: 56px;
  line-height: 0.98;
  letter-spacing: 0.03em;
  text-shadow: 0 0 22px rgba(39, 216, 255, 0.35);
}

.kpi-card__subtitle {
  margin-top: 10px;
  color: #8aa8c7;
  font-size: 14px;
  letter-spacing: 0.08em;
}

.kpi-card--success .kpi-card__value,
.kpi-card--success .kpi-card__icon {
  color: #20c36b;
  text-shadow: 0 0 22px rgba(32, 195, 107, 0.35);
}

.kpi-card--danger .kpi-card__value,
.kpi-card--danger .kpi-card__icon {
  color: #ff6b6b;
  text-shadow: 0 0 24px rgba(178, 34, 34, 0.5);
}

.kpi-card--gold .kpi-card__value,
.kpi-card--gold .kpi-card__icon {
  color: #d4af37;
  text-shadow: 0 0 22px rgba(212, 175, 55, 0.4);
}
</style>
