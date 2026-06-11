<script setup lang="ts">
import { Vue3Lottie } from "vue3-lottie";
import { zhCN } from "@/i18n/zh-CN";
</script>

<template>
  <div class="anim-wrap" role="status" aria-live="polite">
    <div class="lottie-shell denied">
      <Vue3Lottie animation-link="/lottie/denied.json" :height="136" :width="136" :loop="false" no-margin />
    </div>
    <p class="title">{{ zhCN.result.denied }}</p>
    <p class="sub">请正对摄像头、保持单人通行并确保光线充足</p>
  </div>
</template>

<style scoped>
.anim-wrap { text-align: center; color: #fff; }
.lottie-shell {
  width: 154px;
  height: 154px;
  display: grid;
  place-items: center;
  margin: 0 auto;
  border-radius: 42px;
  background: radial-gradient(circle, rgba(249,115,22,0.2), rgba(178,34,34,0.04) 64%, transparent);
  box-shadow: 0 0 34px rgba(249,115,22,0.26);
}
.title { margin: 22px 0 6px; font-size: 22px; font-weight: 800; color: #fed7aa; }
.sub { width: min(340px, 76vw); margin: 0 auto; font-size: 14px; color: rgba(255,255,255,0.72); line-height: 1.6; }
</style>
