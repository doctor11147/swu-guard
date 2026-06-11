<script setup lang="ts">
/**
 * 环境自适应控制页
 * 借鉴 art-design-pro 仪表盘卡片 + soybean-admin 状态卡片
 */
import { Check, Loading, Refresh, Setting } from "@element-plus/icons-vue";
import { ElMessage } from "element-plus";

import { adaptiveApi, type AdaptiveState, type RuntimeRecognitionConfig } from "@/api/adaptive";
import DataCard from "@/components/common/DataCard.vue";
import PageHeader from "@/components/common/PageHeader.vue";

const state = ref<AdaptiveState | null>(null);
const loading = ref(false);

const modeOptions = [
  { value: "off", label: "关闭" },
  { value: "rule_only", label: "纯规则 (Rule-only)" },
  { value: "vlm", label: "VLM (OpenAI)" },
  { value: "vlm_weather", label: "VLM + 天气佐证" },
];

const modeLabel = (m: string) => modeOptions.find((o) => o.value === m)?.label ?? m;
const profileLabel: Record<string, string> = {
  normal: "正常", overcast: "阴天", low_light: "低光照",
  night: "夜间", rain_fog: "雨雾", backlight: "逆光", unsafe: "不安全",
};
const riskLabel: Record<string, string> = {
  low: "低", medium: "中", high: "高", critical: "紧急",
};
const riskTagType = (r: string) =>
  ({ low: "success", medium: "warning", high: "danger", critical: "danger" } as any)[r] || "info";

async function load() {
  loading.value = true;
  try { state.value = await adaptiveApi.state(); }
  finally { loading.value = false; }
}
onMounted(load);

// 抓取一帧摄像头画面（用完即关，不影响其他页面的摄像头流）
async function captureOneFrame(): Promise<string | null> {
  let stream: MediaStream | null = null;
  let video: HTMLVideoElement | null = null;
  try {
    if (!navigator.mediaDevices?.getUserMedia) return null;
    stream = await navigator.mediaDevices.getUserMedia({
      video: { width: { ideal: 640 }, height: { ideal: 480 } }, audio: false,
    });
    video = document.createElement("video");
    video.setAttribute("playsinline", "");
    video.setAttribute("muted", "");
    video.style.position = "fixed"; video.style.top = "-9999px"; video.style.left = "-9999px";
    video.style.width = "1px"; video.style.height = "1px";
    document.body.appendChild(video);
    video.srcObject = stream;
    await video.play();
    // Safari 需要 video 在 DOM 中才能触发 onplaying，加 3 秒超时兜底
    await new Promise<void>((resolve, reject) => {
      const t = setTimeout(() => resolve(), 3000);
      video!.onplaying = () => { clearTimeout(t); resolve(); };
      video!.onerror = () => { clearTimeout(t); reject(new Error("video error")); };
    });
    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth || 640;
    canvas.height = video.videoHeight || 480;
    canvas.getContext("2d")?.drawImage(video, 0, 0);
    const dataUrl = canvas.toDataURL("image/jpeg", 0.7);
    return dataUrl.split(",", 2)[1] || null;
  } catch {
    return null;
  } finally {
    if (stream) stream.getTracks().forEach((t) => t.stop());
    if (video?.parentNode) video.parentNode.removeChild(video);
  }
}

async function doEvaluate() {
  try {
    const frame = await captureOneFrame();
    await adaptiveApi.evaluate(undefined, false, frame || undefined);
    if (frame) {
      ElMessage.success("已用摄像头画面评估");
    } else {
      // 摄像头不可用但评估已用灰帧完成（VLM 会识别为不可用场景）
      // 不弹错误，让用户从"当前生效原因"中看到结果
    }
    await load();
  } catch { ElMessage.error("评估失败"); }
}
async function doApply() {
  try {
    await adaptiveApi.apply();
    ElMessage.success("策略已应用");
    await load();
  } catch { ElMessage.error("应用失败"); }
}
async function toggleMode(mode: string) {
  try {
    await adaptiveApi.updateConfig({
      mode,
      enabled: mode !== "off",
    });
    ElMessage.success(`已切换为 ${modeLabel(mode)}`);
    await load();
  } catch { ElMessage.error("切换失败"); }
}

const baseParams = {
  det_thresh: 0.50, spoof_thresh: 0.85, match_thresh: 0.40,
  quality_thresh: 0.50, consensus_frames: 3,
};
</script>

<template>
  <div class="adaptive-page">
    <PageHeader title="环境自适应控制" subtitle="基于 VLM 视觉先验的环境感知自适应门禁识别控制器">
      <template #actions>
        <el-button :icon="Refresh" @click="load" :loading="loading" plain>刷新</el-button>
      </template>
    </PageHeader>

    <!-- 顶部状态卡片 -->
    <div class="kpi-grid">
      <DataCard>
        <template #header><span class="head">当前模式</span></template>
        <div class="kpi-val">{{ state ? modeLabel(state.mode) : "—" }}</div>
        <div class="kpi-sub">
          <el-tag :type="state?.enabled ? 'success' : 'info'" size="small" effect="light">
            {{ state?.enabled ? '已启用' : '已停用' }}
          </el-tag>
        </div>
      </DataCard>
      <DataCard>
        <template #header><span class="head">环境 Profile</span></template>
        <div :class="['kpi-val', state?.profile ? `text-${state.profile}` : '']">
          {{ state?.profile ? profileLabel[state.profile] : "—" }}
        </div>
      </DataCard>
      <DataCard>
        <template #header><span class="head">风险等级</span></template>
        <div class="kpi-val">
          <el-tag v-if="state" :type="riskTagType(state.risk_level)" size="large" effect="light">
            {{ riskLabel[state.risk_level] }}
          </el-tag>
          <span v-else>—</span>
        </div>
      </DataCard>
      <DataCard>
        <template #header><span class="head">自动放行</span></template>
        <div class="kpi-val">
          <el-tag
            :type="state?.runtime_config?.auto_grant_enabled ? 'success' : 'danger'"
            size="large" effect="light"
          >
            {{ state?.runtime_config?.auto_grant_enabled ? '允许' : '禁止' }}
          </el-tag>
        </div>
        <div v-if="state?.runtime_config?.manual_review" class="kpi-sub text-warn">需要人工复核</div>
      </DataCard>
    </div>

    <!-- 原因 -->
    <DataCard v-if="state?.last_reason" style="margin-top:14px">
      <template #header><span class="head">当前生效原因</span></template>
      <p class="reason">{{ state.last_reason }}</p>
    </DataCard>

    <!-- 模式切换 -->
    <DataCard style="margin-top:14px">
      <template #header><span class="head">模式切换</span></template>
      <div class="mode-row">
        <el-button
          v-for="m in modeOptions" :key="m.value"
          :type="state?.mode === m.value ? 'primary' : ''"
          :plain="state?.mode !== m.value"
          size="small"
          @click="toggleMode(m.value)"
        >{{ m.label }}</el-button>
      </div>
    </DataCard>

    <!-- 参数对比表 -->
    <DataCard style="margin-top:14px">
      <template #header>
        <span class="head">参数对比表</span>
        <span class="dim">Base (基准) → Current (当前生效)</span>
      </template>
      <el-table :data="[
        { key: 'det_thresh',       label: '检测阈值',    unit: '',  low: '可适度降低以减少漏检' },
        { key: 'spoof_thresh',     label: '活体阈值',    unit: '',  low: '不得低于 base' },
        { key: 'match_thresh',     label: '匹配阈值',    unit: '',  low: '不得低于 base' },
        { key: 'quality_thresh',   label: '质量阈值',    unit: '',  low: '复杂环境下提高' },
        { key: 'consensus_frames', label: '共识帧数',    unit: '帧', low: '复杂环境下增加' },
      ]" size="small" :show-header="true"
        :header-cell-style="{ background: 'var(--swu-bg)', color: 'var(--swu-text-2)', fontWeight: 600 }"
      >
        <el-table-column prop="label" label="参数" width="140" />
        <el-table-column label="Base" width="120">
          <template #default="{ row }">
            <span class="mono">{{ (baseParams as any)[row.key] }}</span>
          </template>
        </el-table-column>
        <el-table-column label="Current">
          <template #default="{ row }">
            <span v-if="state?.runtime_config" :class="['mono', (state.runtime_config as any)[row.key] !== (baseParams as any)[row.key] ? 'text-blue' : '']">
              {{ (state.runtime_config as any)[row.key] }}
            </span>
            <span v-else class="dim">—</span>
          </template>
        </el-table-column>
        <el-table-column prop="low" label="安全说明" min-width="200">
          <template #default="{ row }"><span class="dim">{{ row.low }}</span></template>
        </el-table-column>
      </el-table>
    </DataCard>

    <!-- 操作按钮 -->
    <div class="action-bar">
      <el-button :icon="Refresh" @click="doEvaluate" :loading="loading" type="primary">手动评估一次</el-button>
      <el-button :icon="Check" @click="doApply" plain>应用最近策略</el-button>
    </div>
  </div>
</template>

<style scoped>
.adaptive-page {
  animation: slide-up 0.4s cubic-bezier(0.16, 1, 0.3, 1);
  padding-bottom: 40px;
}

.kpi-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 14px;
}
@media (max-width: 1024px) { .kpi-grid { grid-template-columns: repeat(2, 1fr); } }

.head { font-weight: 600; font-size: 13px; }
.dim { font-size: 12px; color: var(--swu-text-3); }
.mono {
  font-family: "Inter", ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 14px;
}

.kpi-val {
  font-size: 22px; font-weight: 700;
  margin-top: 8px;
  font-family: "Inter", ui-sans-serif, system-ui, sans-serif;
}
.kpi-sub { margin-top: 6px; }
.text-warn { color: var(--swu-warning); font-size: 12px; }
.text-blue { color: var(--swu-blue); font-weight: 600; }

.reason {
  font-size: 13px; color: var(--swu-text-2);
  line-height: 1.7; margin: 0;
  white-space: pre-wrap;
}

.mode-row { display: flex; gap: 8px; flex-wrap: wrap; }

.action-bar {
  display: flex; gap: 10px; margin-top: 20px;
}

@keyframes slide-up {
  from { opacity: 0; transform: translateY(8px); }
  to   { opacity: 1; transform: translateY(0); }
}
</style>
