<!-- 参考来源: skills/art-design-pro/src/views/index -->
<script setup lang="ts">
import { ArrowRight, Location } from "@element-plus/icons-vue";

import { zhCN } from "@/i18n/zh-CN";
import type { GateOut } from "@/api/types";

const props = defineProps<{
  gate: GateOut;
}>();

const statusMeta = computed(() => {
  if (props.gate.status === "online") {
    return { label: "active", className: "is-active" };
  }
  if (props.gate.status === "offline") {
    return { label: "maintenance", className: "is-maintenance" };
  }
  return { label: "disabled", className: "is-disabled" };
});
</script>

<template>
  <RouterLink class="gate-card" :to="`/gates/${gate.id}/recognize`">
    <div class="card-top">
      <span class="status-badge" :class="statusMeta.className">
        {{ statusMeta.label }}
      </span>
      <el-icon class="arrow"><ArrowRight /></el-icon>
    </div>
    <h2>{{ gate.name }}</h2>
    <p class="location">
      <el-icon><Location /></el-icon>
      <span>{{ gate.location || "位置未配置" }}</span>
    </p>
    <div class="card-footer">
      <span>{{ gate.campus === "beibei" ? "北碚校区" : "荣昌校区" }}</span>
      <strong>{{ zhCN.home.recognizeEntry }}</strong>
    </div>
  </RouterLink>
</template>

<style scoped>
.gate-card {
  display: flex;
  flex-direction: column;
  min-height: 188px;
  padding: 24px;
  border: 1px solid rgba(27, 79, 142, 0.08);
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.92);
  color: inherit;
  text-decoration: none;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.06);
  transition: transform 200ms cubic-bezier(0.4, 0, 0.2, 1),
    box-shadow 200ms cubic-bezier(0.4, 0, 0.2, 1),
    border-color 200ms cubic-bezier(0.4, 0, 0.2, 1);
}

.gate-card:hover {
  transform: translateY(-4px);
  border-color: rgba(27, 79, 142, 0.2);
  box-shadow: 0 12px 32px rgba(0, 0, 0, 0.12);
}

.card-top,
.card-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.status-badge {
  display: inline-flex;
  align-items: center;
  min-height: 24px;
  padding: 0 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
}

.is-active {
  color: #166534;
  background: #dcfce7;
}

.is-maintenance {
  color: #92400e;
  background: #fef3c7;
}

.is-disabled {
  color: #4b5563;
  background: #e5e7eb;
}

.arrow {
  color: var(--xw-primary);
}

h2 {
  margin: 28px 0 12px;
  color: var(--xw-text);
  font-size: 22px;
  line-height: 1.28;
  letter-spacing: 0;
}

.location {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin: 0;
  min-height: 44px;
  color: var(--xw-muted);
  font-size: 14px;
  line-height: 1.55;
}

.card-footer {
  margin-top: auto;
  padding-top: 20px;
  color: var(--xw-muted);
  font-size: 13px;
}

.card-footer strong {
  color: var(--xw-accent);
}
</style>
