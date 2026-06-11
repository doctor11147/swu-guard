<script setup lang="ts">
import NumberFlow from "@number-flow/vue";
import type { Format } from "@number-flow/vue";
import { usePreferredReducedMotion } from "@vueuse/core";
import { computed } from "vue";

const props = withDefaults(defineProps<{
  value: number;
  prefix?: string;
  suffix?: string;
  decimals?: number;
}>(), {
  prefix: "",
  suffix: "",
  decimals: 0,
});

const motion = usePreferredReducedMotion();
const shouldReduceMotion = computed(() => motion.value === "reduce");

const formatter = computed<Format>(() => ({
  notation: "standard",
  maximumFractionDigits: props.decimals,
  minimumFractionDigits: props.decimals,
}));

const staticText = computed(() => {
  const formatted = props.value.toLocaleString("zh-CN", formatter.value);
  return `${props.prefix}${formatted}${props.suffix}`;
});
</script>

<template>
  <span class="kpi-number" aria-live="polite">
    <span v-if="shouldReduceMotion">{{ staticText }}</span>
    <NumberFlow
      v-else
      :value="value"
      :prefix="prefix"
      :suffix="suffix"
      :format="formatter"
      locales="zh-CN"
      will-change
    />
  </span>
</template>

<style scoped>
.kpi-number {
  display: inline-flex;
  align-items: baseline;
  min-width: 0;
  font-variant-numeric: tabular-nums;
}
</style>
