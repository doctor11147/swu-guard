<script setup lang="ts">
import { Vue3Lottie } from "vue3-lottie";
import { zhCN } from "@/i18n/zh-CN";

defineProps<{ name?: string }>();
</script>

<template>
  <div class="anim-wrap" role="status" aria-live="polite">
    <div class="lottie-shell success">
      <Vue3Lottie animation-link="/lottie/success-checkmark.json" :height="138" :width="138" :loop="false" no-margin />
      <div class="gate-flare" />
    </div>
    <p class="title">{{ zhCN.result.granted }}<template v-if="name"> · {{ name }}</template></p>
    <p class="sub">闸机已开启，请有序通行</p>
  </div>
</template>

<style scoped>
.anim-wrap { text-align: center; color: #fff; }
.lottie-shell {
  position: relative;
  width: 154px;
  height: 154px;
  display: grid;
  place-items: center;
  margin: 0 auto;
  border-radius: 42px;
  background: radial-gradient(circle, rgba(32,195,107,0.18), rgba(32,195,107,0.03) 64%, transparent);
}
.gate-flare {
  position: absolute;
  inset: 18px;
  border-radius: 32px;
  border: 1px solid rgba(212,175,55,0.72);
  box-shadow: 0 0 34px rgba(32,195,107,0.42), inset 0 0 24px rgba(212,175,55,0.2);
  animation: gate-open 0.9s 0.25s cubic-bezier(0.22,1,0.36,1) both;
}
@keyframes gate-open {
  from { opacity: 0; transform: scaleX(0.34) scaleY(0.92); }
  to { opacity: 1; transform: scaleX(1) scaleY(1); }
}
.title { margin: 22px 0 6px; font-size: 22px; font-weight: 800; color: #dcfce7; }
.sub { margin: 0; font-size: 14px; color: rgba(255,255,255,0.72); }
@media (prefers-reduced-motion: reduce) { .gate-flare { animation: none; } }
</style>
