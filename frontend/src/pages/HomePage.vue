<!-- 参考来源: skills/art-design-pro/src/views/index -->
<script setup lang="ts">
import BrandHeader from "@/components/home/BrandHeader.vue";
import CampusGateMap from "@/components/home/CampusGateMap.vue";
import CornerLoginEntries from "@/components/home/CornerLoginEntries.vue";
import GateList from "@/components/home/GateList.vue";
import { gateFocusKey, useGateFocus } from "@/components/home/useGateFocus";
import { gatesApi } from "@/api/gates";
import type { GateOut } from "@/api/types";
import { zhCN } from "@/i18n/zh-CN";

const gates = ref<GateOut[]>([]);
const loading = ref(true);
const error = ref("");
const gateFocus = useGateFocus();

provide(gateFocusKey, gateFocus);

const isAbnormal = computed(() => !loading.value && !error.value && gates.value.length !== 7);

async function loadGates() {
  loading.value = true;
  error.value = "";
  try {
    gates.value = await gatesApi.publicList();
  } catch {
    error.value = zhCN.home.gateError;
  } finally {
    loading.value = false;
  }
}

onMounted(loadGates);
</script>

<template>
  <main class="home-page">
    <div class="home-shell">
      <div class="top-row">
        <BrandHeader />
        <CornerLoginEntries />
      </div>

      <section class="gate-section" aria-label="门禁入口">
        <div v-if="loading" class="state-box">{{ zhCN.home.gateLoading }}</div>
        <div v-else-if="error" class="state-box is-error">
          {{ error }}
          <button type="button" @click="loadGates">重试</button>
        </div>
        <div v-else class="gate-layout">
          <aside class="gate-panel">
            <div class="panel-head">
              <h2>选择门禁</h2>
              <p>请选择当前所在入口，进入单门刷脸识别。</p>
            </div>
            <GateList :gates="gates" />
            <p v-if="isAbnormal" class="abnormal-note">
              {{ zhCN.home.gateCountAbnormal }} · 当前 {{ gates.length }} 个
            </p>
          </aside>

          <div class="map-panel">
            <CampusGateMap :gates="gates" />
          </div>
        </div>
      </section>

      <footer>{{ zhCN.home.footer }}</footer>
    </div>
  </main>
</template>

<style scoped>
:global(:root) {
  --xw-primary: #1b4f8e;
  --xw-accent: #2e7d5b;
  --xw-text: #172033;
  --xw-muted: #637083;
  --xw-bg: #f4f8fb;
}

:global(body) {
  font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Microsoft YaHei", sans-serif;
}

.home-page {
  min-height: 100vh;
  background:
    linear-gradient(180deg, rgba(27, 79, 142, 0.08), rgba(46, 125, 91, 0.05)),
    var(--xw-bg);
}

.home-shell {
  width: min(1280px, calc(100% - 32px));
  margin: 0 auto;
  padding: 24px 0 16px;
}

.top-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 24px;
  align-items: start;
}

.gate-section {
  margin-top: 48px;
}

.gate-layout {
  display: grid;
  grid-template-columns: minmax(340px, 400px) minmax(0, 1fr);
  gap: 24px;
  align-items: stretch;
}

.gate-panel,
.map-panel {
  border: 1px solid rgba(27, 79, 142, 0.08);
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.72);
  box-shadow:
    0 1px 3px rgba(0, 0, 0, 0.03),
    0 10px 28px rgba(27, 79, 142, 0.08);
}

.gate-panel {
  padding: 20px;
}

.map-panel {
  padding: 14px;
  display: flex;
  align-items: center;
}

.map-panel :deep(.campus-map) {
  width: 100%;
}

.panel-head {
  margin-bottom: 18px;
  padding-bottom: 15px;
  border-bottom: 1px solid rgba(27, 79, 142, 0.08);
}

.panel-head h2 {
  margin: 0;
  color: var(--xw-text);
  font-size: 24px;
  line-height: 1.2;
  letter-spacing: 0;
}

.panel-head p {
  margin: 8px 0 0;
  color: var(--xw-muted);
  line-height: 1.5;
}

.abnormal-note {
  width: 100%;
  margin: 14px 0 0;
  color: #92400e;
  font-size: 13px;
  font-weight: 700;
}

.state-box {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 220px;
  border: 1px dashed rgba(27, 79, 142, 0.22);
  border-radius: 16px;
  color: var(--xw-muted);
  background: rgba(255, 255, 255, 0.68);
}

.state-box.is-error {
  flex-direction: column;
  gap: 16px;
  color: #b91c1c;
}

.state-box button {
  min-height: 38px;
  padding: 0 16px;
  border: 0;
  border-radius: 12px;
  color: #fff;
  background: var(--xw-primary);
  cursor: pointer;
}

footer {
  padding: 48px 0 8px;
  color: var(--xw-muted);
  text-align: center;
  font-size: 13px;
}

@media (max-width: 760px) {
  .top-row {
    grid-template-columns: 1fr;
    display: grid;
  }

  .home-shell {
    width: min(100% - 24px, 1280px);
    padding-top: 16px;
  }

  .gate-section {
    margin-top: 32px;
  }

  .gate-layout {
    grid-template-columns: 1fr;
  }

  .map-panel {
    order: 1;
    align-items: stretch;
  }

  .gate-panel {
    order: 2;
  }
}

@media (min-width: 768px) and (max-width: 1023px) {
  .gate-layout {
    grid-template-columns: 1fr;
  }

  .map-panel {
    order: 1;
  }

  .gate-panel {
    order: 2;
  }
}
</style>
