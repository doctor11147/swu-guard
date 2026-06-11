<script setup lang="ts">
import { Decoration8, Decoration10 } from "@kjgl77/datav-vue3";
import "@kjgl77/datav-vue3/dist/style.css";

import { screenPalette } from "@/styles/motion-tokens";

withDefaults(defineProps<{
  clockText: string;
  schoolName?: string;
  gatesOnline: number;
  gatesTotal: number;
  lastUpdated?: string;
}>(), {
  schoolName: "西南大学",
  lastUpdated: "--:--:--",
});

const decorColor = [screenPalette.cyan, screenPalette.gold];
</script>

<template>
  <header class="screen-header">
    <div class="screen-header__wing screen-header__wing--left">
      <Decoration10 class="screen-header__line" :color="decorColor" />
      <div class="screen-header__brand">
        <img src="/brand/swu-logo.png" class="screen-header__logo" alt="西南大学" />
        <div>
          <div class="screen-header__school">{{ schoolName }}</div>
          <div class="screen-header__sub">SWU-Guard</div>
        </div>
      </div>
    </div>

    <div class="screen-header__center">
      <Decoration8 class="screen-header__deco" :color="decorColor" />
      <div class="screen-header__title-wrap">
        <div class="screen-header__eyebrow">SWU-Guard</div>
        <h1 class="screen-header__title">西小卫</h1>
        <div class="screen-header__scan" />
      </div>
      <Decoration8 class="screen-header__deco" :reverse="true" :color="decorColor" />
    </div>

    <div class="screen-header__wing screen-header__wing--right">
      <Decoration10 class="screen-header__line screen-header__line--reverse" :color="decorColor" />
      <div class="screen-header__status">
        <div class="screen-header__clock">{{ clockText }}</div>
        <div class="screen-header__meta">
          在线门禁 {{ gatesOnline }}/{{ gatesTotal }} · 刷新 {{ lastUpdated }}
        </div>
      </div>
    </div>
  </header>
</template>

<style scoped>
.screen-header {
  display: grid;
  grid-template-columns: 500px 1fr 500px;
  align-items: center;
  height: 118px;
  gap: 18px;
  color: #eaf4ff;
}

.screen-header__wing {
  position: relative;
  display: flex;
  height: 100%;
  align-items: center;
}

.screen-header__wing--left {
  justify-content: flex-start;
  padding-left: 18px;
}

.screen-header__wing--right {
  justify-content: flex-end;
  padding-right: 18px;
}

.screen-header__line {
  position: absolute;
  right: 0;
  bottom: 8px;
  left: 0;
  height: 22px;
  opacity: 0.8;
}

.screen-header__line--reverse {
  transform: scaleX(-1);
}

.screen-header__brand {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  gap: 18px;
}

.screen-header__logo {
  width: 72px;
  height: 72px;
  object-fit: contain;
  filter: drop-shadow(0 0 18px rgba(39, 216, 255, 0.34)) brightness(1.08);
}

.screen-header__school {
  font-size: 24px;
  font-weight: 800;
  letter-spacing: 0.14em;
}

.screen-header__sub {
  margin-top: 6px;
  color: #8aa8c7;
  font-size: 13px;
  letter-spacing: 0.2em;
  text-transform: uppercase;
}

.screen-header__center {
  display: grid;
  grid-template-columns: 190px 1fr 190px;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.screen-header__deco {
  width: 190px;
  height: 56px;
  opacity: 0.86;
}

.screen-header__title-wrap {
  position: relative;
  min-width: 0;
  text-align: center;
}

.screen-header__eyebrow {
  color: #d4af37;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.34em;
  opacity: 0.92;
}

.screen-header__title {
  margin: 6px 0 0;
  background: linear-gradient(180deg, #ffffff 0%, #b9e8ff 44%, #27d8ff 100%);
  background-clip: text;
  color: transparent;
  font-size: 42px;
  font-weight: 900;
  letter-spacing: 0.2em;
  line-height: 1;
  text-shadow: 0 0 32px rgba(39, 216, 255, 0.25);
}

.screen-header__scan {
  width: 76%;
  height: 2px;
  margin: 14px auto 0;
  background: linear-gradient(90deg, transparent, #27d8ff, #d4af37, #27d8ff, transparent);
  box-shadow: 0 0 18px rgba(39, 216, 255, 0.55);
}

.screen-header__status {
  position: relative;
  z-index: 1;
  text-align: right;
}

.screen-header__clock {
  color: #27d8ff;
  font-family: "DIN Alternate", "Arial Narrow", monospace;
  font-size: 28px;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-shadow: 0 0 20px rgba(39, 216, 255, 0.42);
}

.screen-header__meta {
  margin-top: 8px;
  color: #8aa8c7;
  font-size: 13px;
  letter-spacing: 0.1em;
}
</style>
