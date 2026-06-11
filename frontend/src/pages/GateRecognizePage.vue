<script setup lang="ts">
import { ArrowLeft } from "@element-plus/icons-vue";
import type { GateOut, PublicRecognizeDecision } from "@/api/types";
import { gatesApi } from "@/api/gates";
import type { GateRecognitionResult } from "@/composables/useGateRecognition";
import { zhCN } from "@/i18n/zh-CN";
import CameraStage from "@/components/recognize/CameraStage.vue";
import ResultOverlay from "@/components/recognize/ResultOverlay.vue";

const route = useRoute();
const router = useRouter();
const gateId = computed(() => Number(route.params.gateId));

const gate = ref<GateOut | null>(null);
const gateLoading = ref(true);
const gateError = ref("");
const resultDecision = ref<PublicRecognizeDecision | null>(null);
const resultName = ref("");
const isSpoof = ref(false);

const gateOnline = computed(() => gate.value?.status === "online");

async function loadGate() {
  gateLoading.value = true;
  gateError.value = "";
  try {
    gate.value = await gatesApi.publicGet(gateId.value);
  } catch {
    gateError.value = zhCN.recognize.gateError;
  } finally {
    gateLoading.value = false;
  }
}

function onResult(result: GateRecognitionResult) {
  resultDecision.value = result.decision;
  resultName.value = result.name;
  isSpoof.value = result.spoof;
}

function onResultDone() {
  resultDecision.value = null;
}

onMounted(loadGate);
</script>

<template>
  <main class="recognize-page">
    <div class="shell">
      <header class="head-bar">
        <el-button :icon="ArrowLeft" text class="back-btn" @click="router.push('/')">返回首页</el-button>
        <template v-if="gateLoading">
          <span class="dim">{{ zhCN.recognize.loadingGate }}</span>
        </template>
        <template v-else-if="gate">
          <div class="gate-info">
            <span class="gate-status" :class="gateOnline ? 'on' : 'off'" />
            <div>
              <strong>{{ zhCN.recognize.titlePrefix }} · {{ gate.name }}</strong>
              <p>{{ gate.location || '西南大学校园门禁' }}</p>
            </div>
          </div>
        </template>
        <span v-else class="dim">{{ gateError || zhCN.recognize.gateError }}</span>
      </header>

      <CameraStage
        :gate-id="gate?.id ?? null"
        :gate-code="gate?.code ?? null"
        :gate-name="gate?.name"
        :gate-online="gateOnline"
        @result="onResult"
      />

      <ResultOverlay
        v-if="resultDecision"
        :decision="resultDecision"
        :name="resultName"
        :spoof="isSpoof"
        @done="onResultDone"
      />
    </div>
  </main>
</template>

<style scoped>
.recognize-page {
  min-height: 100vh;
  overflow-x: hidden;
  background:
    radial-gradient(circle at 18% 12%, rgba(212, 175, 55, 0.18), transparent 24%),
    radial-gradient(circle at 82% 6%, rgba(0, 61, 122, 0.22), transparent 28%),
    linear-gradient(180deg, #eff6fb 0%, #f8fbfd 46%, #eaf3f8 100%);
}
.shell {
  width: min(1280px, calc(100% - 48px));
  margin: 0 auto;
  padding: 18px 0 32px;
}
.head-bar {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-bottom: 18px;
  min-height: 48px;
}
.back-btn {
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.62);
  box-shadow: 0 8px 24px rgba(0, 61, 122, 0.08);
}
.dim {
  color: var(--xw-muted, #637083);
  font-size: 14px;
}
.gate-info {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}
.gate-info strong {
  display: block;
  color: #172033;
  font-size: 18px;
  line-height: 1.2;
}
.gate-info p {
  margin: 4px 0 0;
  color: #637083;
  font-size: 12px;
}
.gate-status {
  width: 11px;
  height: 11px;
  border-radius: 50%;
  flex-shrink: 0;
}
.gate-status.on  { background: #52C41A; box-shadow: 0 0 10px rgba(82,196,26,0.62); }
.gate-status.off { background: #FAAD14; box-shadow: 0 0 10px rgba(250,173,20,0.48); }

@media (max-width: 680px) {
  .shell { width: min(100% - 20px, 1280px); padding-top: 12px; }
  .head-bar { align-items: flex-start; }
  .gate-info strong { font-size: 16px; }
}
</style>
