<script setup lang="ts">
import { computed } from "vue";
import { Vue3Lottie } from "vue3-lottie";
import { zhCN } from "@/i18n/zh-CN";

const props = defineProps<{ stopped?: boolean }>();
const title = computed(() => props.stopped ? zhCN.result.network : "识别服务重连中…");
</script>

<template>
  <div class="anim-wrap" role="status" aria-live="polite">
    <div class="lottie-shell network" :class="{ stopped }">
      <Vue3Lottie animation-link="/lottie/network-error.json" :height="132" :width="132" :loop="!stopped" no-margin />
    </div>
    <p class="title">{{ title }}</p>
    <p class="sub">请确认后端服务与网络连接正常，系统将自动恢复</p>
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
  background: radial-gradient(circle, rgba(148,163,184,0.22), rgba(15,23,42,0.04) 64%, transparent);
  box-shadow: 0 0 34px rgba(148,163,184,0.22);
}
.lottie-shell.stopped { filter: grayscale(0.3); }
.title { margin: 22px 0 6px; font-size: 22px; font-weight: 800; color: #e2e8f0; }
.sub { width: min(340px, 76vw); margin: 0 auto; font-size: 14px; color: rgba(255,255,255,0.72); line-height: 1.6; }
</style>
