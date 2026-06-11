<script setup lang="ts">
import { Vue3Lottie } from "vue3-lottie";
import { zhCN } from "@/i18n/zh-CN";
</script>

<template>
  <div class="anim-wrap" role="alert" aria-live="assertive">
    <div class="lottie-shell spoof">
      <Vue3Lottie animation-link="/lottie/spoof-warning.json" :height="138" :width="138" :loop="true" no-margin />
      <span class="alarm" />
    </div>
    <p class="title">{{ zhCN.result.spoof }}</p>
    <p class="sub">检测到非真人或屏幕翻拍风险，本次通行已拒绝</p>
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
  background: radial-gradient(circle, rgba(239,68,68,0.22), rgba(178,34,34,0.04) 64%, transparent);
  box-shadow: 0 0 40px rgba(239,68,68,0.32);
}
.alarm {
  position: absolute;
  inset: 0;
  border-radius: 42px;
  border: 1px solid rgba(239,68,68,0.72);
  animation: alarm-ping 1s ease-out infinite;
}
@keyframes alarm-ping { to { opacity: 0; transform: scale(1.22); } }
.title { margin: 22px 0 6px; font-size: 22px; font-weight: 900; color: #fecaca; }
.sub { width: min(340px, 76vw); margin: 0 auto; font-size: 14px; color: rgba(255,255,255,0.72); line-height: 1.6; }
@media (prefers-reduced-motion: reduce) { .alarm { animation: none; } }
</style>
