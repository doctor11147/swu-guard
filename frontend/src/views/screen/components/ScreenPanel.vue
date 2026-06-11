<script setup lang="ts">
import { BorderBox10, BorderBox12, BorderBox13, Decoration5 } from "@kjgl77/datav-vue3";
import "@kjgl77/datav-vue3/dist/style.css";
import { computed } from "vue";

import { screenPalette, swuMotionColors } from "@/styles/motion-tokens";

const props = withDefaults(defineProps<{
  title?: string;
  variant?: "primary" | "accent" | "danger" | "compact";
  height?: string;
  padded?: boolean;
}>(), {
  title: "",
  variant: "primary",
  height: "100%",
  padded: true,
});

const boxComponent = computed(() => {
  if (props.variant === "accent") return BorderBox13;
  if (props.variant === "danger") return BorderBox10;
  return BorderBox12;
});

const borderColors = computed(() => {
  if (props.variant === "danger") return [swuMotionColors.danger, screenPalette.gold];
  if (props.variant === "accent") return [screenPalette.gold, screenPalette.cyan];
  return [swuMotionColors.primary, screenPalette.cyan];
});

const panelStyle = computed(() => ({ height: props.height }));
</script>

<template>
  <section class="screen-panel" :class="`screen-panel--${variant}`" :style="panelStyle">
    <component
      :is="boxComponent"
      class="screen-panel__box"
      :color="borderColors"
      background-color="rgba(0, 0, 0, 0)"
    >
      <div class="screen-panel__inner" :class="{ 'screen-panel__inner--padded': padded }">
        <header v-if="title || $slots.meta" class="screen-panel__header">
          <div class="screen-panel__title">
            <span class="screen-panel__title-mark" />
            <span>{{ title }}</span>
          </div>
          <Decoration5 class="screen-panel__decor" :color="borderColors" />
          <div v-if="$slots.meta" class="screen-panel__meta">
            <slot name="meta" />
          </div>
        </header>
        <div class="screen-panel__body">
          <slot />
        </div>
      </div>
    </component>
  </section>
</template>

<style scoped>
.screen-panel {
  position: relative;
  min-height: 0;
  overflow: hidden;
  border-radius: 18px;
  background:
    linear-gradient(145deg, rgba(39, 216, 255, 0.08), transparent 32%),
    linear-gradient(180deg, rgba(0, 61, 122, 0.2), rgba(0, 20, 43, 0.72));
  box-shadow: inset 0 0 28px rgba(39, 216, 255, 0.05), 0 18px 40px rgba(0, 0, 0, 0.24);
}

.screen-panel::before {
  content: "";
  position: absolute;
  inset: 10px;
  pointer-events: none;
  border-radius: 14px;
  background: linear-gradient(90deg, transparent, rgba(39, 216, 255, 0.12), transparent);
  opacity: 0.35;
  transform: translateX(-35%);
}

.screen-panel--danger {
  background:
    radial-gradient(circle at 10% 0%, rgba(178, 34, 34, 0.22), transparent 44%),
    linear-gradient(180deg, rgba(0, 61, 122, 0.2), rgba(0, 20, 43, 0.76));
}

.screen-panel__box {
  display: block;
  width: 100%;
  height: 100%;
}

.screen-panel__box :deep(.border-box-content) {
  width: 100%;
  height: 100%;
}

.screen-panel__inner {
  position: relative;
  z-index: 1;
  display: flex;
  width: 100%;
  height: 100%;
  min-height: 0;
  flex-direction: column;
}

.screen-panel__inner--padded {
  padding: 24px 26px;
}

.screen-panel__header {
  display: grid;
  grid-template-columns: auto minmax(80px, 1fr) auto;
  align-items: center;
  gap: 16px;
  min-height: 32px;
  margin-bottom: 16px;
}

.screen-panel__title {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  color: #eaf4ff;
  font-size: 18px;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-shadow: 0 0 18px rgba(39, 216, 255, 0.35);
}

.screen-panel__title-mark {
  width: 5px;
  height: 20px;
  border-radius: 999px;
  background: linear-gradient(180deg, #27d8ff, #d4af37);
  box-shadow: 0 0 16px rgba(39, 216, 255, 0.55);
}

.screen-panel__decor {
  width: 100%;
  height: 22px;
  opacity: 0.74;
}

.screen-panel__meta {
  color: #8aa8c7;
  font-size: 12px;
  letter-spacing: 0.08em;
  white-space: nowrap;
}

.screen-panel__body {
  position: relative;
  flex: 1;
  min-height: 0;
}

@media (prefers-reduced-motion: reduce) {
  .screen-panel::before {
    display: none;
  }
}
</style>
