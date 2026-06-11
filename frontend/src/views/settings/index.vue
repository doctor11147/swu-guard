<script setup lang="ts">
/** 系统配置 · 阈值滑块 + KV 配置面板。 */
import { Refresh } from "@element-plus/icons-vue";
import { ElMessage } from "element-plus";

import { systemApi } from "@/api/system";
import type { ConfigOut } from "@/api/types";
import DataCard from "@/components/common/DataCard.vue";
import PageHeader from "@/components/common/PageHeader.vue";

const configs = ref<ConfigOut[]>([]);
const loading = ref(false);

async function load() {
  loading.value = true;
  try { configs.value = await systemApi.configs(); }
  finally { loading.value = false; }
}
onMounted(load);

const map = computed(() => {
  const m: Record<string, ConfigOut> = {};
  for (const c of configs.value) m[c.config_key] = c;
  return m;
});

const matchThreshold = computed(() =>
  (map.value["recognition.match_threshold"]?.value_json?.value as number) ?? 0.4);
const realThreshold = computed(() =>
  (map.value["recognition.spoof_threshold"]?.value_json?.value as number) ?? 0.85);
const antiSpoofEnabled = computed(() =>
  (map.value["recognition.anti_spoof_enabled"]?.value_json?.value as boolean) ?? true);
const embedderModel = computed(() =>
  (map.value["recognition.embedder_model"]?.value_json?.value as string) ?? "edgeface_s_gamma_05");
const snapshotDays = computed(() =>
  (map.value["recognition.snapshot_keep_days"]?.value_json?.value as number) ?? 90);

async function save(key: string, value: unknown, toast = true) {
  try {
    await systemApi.setConfig(key, value);
    if (toast) ElMessage.success("已保存");
    await load();
  } catch { /* axios 拦截器统一弹错 */ }
}

const modelOptions = [
  { value: "edgeface_xxs",         label: "EdgeFace · XXS (1.24M)" },
  { value: "edgeface_xs_gamma_06", label: "EdgeFace · XS (1.77M, 默认轻量)" },
  { value: "edgeface_s_gamma_05",  label: "EdgeFace · S  (3.65M, 推荐)" },
  { value: "edgeface_base",        label: "EdgeFace · Base (18.2M, 高精度)" },
];

const schoolKeys = [
  "school.name_zh", "school.name_en", "school.code",
  "school.motto", "school.spirit", "school.url",
];
const schoolItems = computed(() =>
  schoolKeys.map((k) => map.value[k]).filter(Boolean),
);

function configValue(c: ConfigOut): unknown {
  return c.value_json?.value;
}
</script>

<template>
  <div>
    <PageHeader title="系统配置" subtitle="阈值热更新无需重启 · 仅 superadmin / admin 可改">
      <template #actions>
        <el-button :icon="Refresh" circle title="刷新" @click="load" />
      </template>
    </PageHeader>

    <DataCard v-loading="loading">
      <template #header>
        <span class="head">识别参数</span>
        <span class="dim">写入数据库后下次请求即生效</span>
      </template>

      <div class="form">
        <div class="field">
          <div class="label">
            <span>匹配阈值 (cosine)</span>
            <span class="value">{{ matchThreshold.toFixed(2) }}</span>
          </div>
          <el-slider
            :model-value="matchThreshold"
            :min="0" :max="1" :step="0.01"
            :marks="{ 0.3: '0.30', 0.4: '0.40 默认', 0.5: '0.50', 0.6: '0.60' }"
            @change="(v) => save('recognition.match_threshold', v as number)"
          />
          <p class="hint">越高越严格；LFW 1:1 最优 ~0.34，1:N 推荐 ≥ 0.40</p>
        </div>

        <div class="field">
          <div class="label">
            <span>活体真实度阈值</span>
            <span class="value">{{ realThreshold.toFixed(2) }}</span>
          </div>
          <el-slider
            :model-value="realThreshold"
            :min="0" :max="1" :step="0.01"
            :marks="{ 0.7: '0.70', 0.85: '0.85 默认', 0.95: '0.95' }"
            @change="(v) => save('recognition.spoof_threshold', v as number)"
          />
          <p class="hint">MiniFAS softmax 真实度，越高越严</p>
        </div>

        <div class="row">
          <div class="row-item">
            <div class="label">
              <span>启用活体检测</span>
              <el-switch
                :model-value="antiSpoofEnabled"
                inline-prompt active-text="开" inactive-text="关"
                @change="(v) => save('recognition.anti_spoof_enabled', !!v)"
              />
            </div>
            <p class="hint">关闭后将跳过 MiniFAS 校验</p>
          </div>

          <div class="row-item">
            <div class="label">
              <span>抓拍保留天数</span>
              <el-input-number
                :model-value="snapshotDays"
                :min="1" :max="365" size="small"
                @change="(v) => v != null && save('recognition.snapshot_keep_days', v)"
              />
            </div>
            <p class="hint">超过此天数的现场抓拍图将清理</p>
          </div>
        </div>

        <div class="field">
          <div class="label"><span>当前嵌入模型</span></div>
          <el-radio-group
            :model-value="embedderModel"
            @change="(v) => v && save('recognition.embedder_model', String(v))"
          >
            <el-radio-button v-for="m in modelOptions" :key="m.value" :value="m.value">
              {{ m.label }}
            </el-radio-button>
          </el-radio-group>
          <p class="hint">切换模型后需重启后端以重新加载权重</p>
        </div>
      </div>
    </DataCard>

    <DataCard>
      <template #header>
        <span class="head">学校信息</span>
        <span class="dim">只读 / 由数据库 seed 提供</span>
      </template>
      <el-descriptions :column="2" border>
        <el-descriptions-item
          v-for="c in schoolItems" :key="c.config_key"
          :label="c.description || c.config_key"
        >
          {{ configValue(c) }}
        </el-descriptions-item>
      </el-descriptions>
    </DataCard>
  </div>
</template>

<style scoped>
.head { font-weight: 600; }
.dim { font-size: 12px; color: var(--swu-text-3); }

.form { display: flex; flex-direction: column; gap: 24px; padding: 4px 8px; }
.field { display: flex; flex-direction: column; gap: 4px; }
.label {
  display: flex; justify-content: space-between; align-items: center;
  font-size: 13px; color: var(--swu-text); font-weight: 500;
  margin-bottom: 4px;
}
.value {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  background: var(--swu-blue-50); color: var(--swu-blue);
  padding: 2px 10px; border-radius: 4px; font-size: 13px;
}
.hint { font-size: 12px; color: var(--swu-text-3); margin: 6px 0 0; }

.row { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; }
.row-item { display: flex; flex-direction: column; }
</style>
