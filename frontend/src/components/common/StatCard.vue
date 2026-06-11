<script setup lang="ts">
/**
 * 统计卡片 · 借鉴 art-design-pro art-stats-card
 * - 图标在彩色圆角方块中
 * - 巨型数字（Inter 字体）
 * - 描述文字
 * - hover 上浮 + 阴影
 */
import * as Icons from "@element-plus/icons-vue";

defineProps<{
  label: string;
  value: number | string;
  icon?: string;
  hint?: string;
  tone?: "blue" | "red" | "gold" | "green" | "cyan";
  delta?: string;
  deltaUp?: boolean;
}>();

function getIcon(name?: string) {
  if (!name) return Icons.DataLine;
  return (Icons as Record<string, unknown>)[name] ?? Icons.DataLine;
}
</script>

<template>
  <div :class="['stat-card', `tone-${tone || 'blue'}`]">
    <div class="card-inner">
      <div v-if="icon" :class="['stat-icon', `tone-${tone || 'blue'}`]">
        <el-icon :size="20">
          <component :is="getIcon(icon)" />
        </el-icon>
      </div>
      <div class="stat-body">
        <div class="stat-value">{{ value }}</div>
        <div class="stat-label">{{ label }}</div>
        <div v-if="hint" class="stat-hint">{{ hint }}</div>
        <div v-if="delta" :class="['stat-delta', deltaUp ? 'up' : 'down']">
          <span class="delta-arrow">{{ deltaUp ? '↑' : '↓' }}</span>
          {{ delta }}
        </div>
      </div>
    </div>
    <!-- 背景光晕 -->
    <div class="glow" />
  </div>
</template>

<style scoped>
.stat-card {
  position: relative;
  background: var(--swu-bg-elev);
  border: 1px solid var(--swu-border);
  border-radius: var(--swu-radius-lg);
  padding: 20px 22px;
  overflow: hidden;
  transition: all var(--swu-transition);
  box-shadow: var(--swu-shadow-sm);
}
.stat-card:hover {
  transform: translateY(-3px);
  box-shadow: var(--swu-shadow-lg);
  border-color: rgba(0, 61, 122, 0.12);
}
/* 背景光晕 */
.glow {
  position: absolute; top: -40px; right: -40px;
  width: 140px; height: 140px; border-radius: 50%;
  filter: blur(48px); opacity: 0.10;
  pointer-events: none;
  transition: opacity 0.2s ease;
}
.stat-card:hover .glow { opacity: 0.18; }
.tone-blue .glow  { background: #003D7A; }
.tone-red .glow   { background: #B22222; }
.tone-gold .glow  { background: #D4AF37; }
.tone-green .glow { background: #52C41A; }
.tone-cyan .glow  { background: #00838F; }

.card-inner {
  position: relative;
  display: flex; align-items: flex-start; gap: 16px;
}

/* 图标方块 */
.stat-icon {
  width: 46px; height: 46px;
  border-radius: 12px;
  display: inline-flex; align-items: center; justify-content: center;
  flex-shrink: 0;
  color: #fff;
}
.stat-icon.tone-blue  { background: linear-gradient(135deg, #003D7A, #1565C0); }
.stat-icon.tone-red   { background: linear-gradient(135deg, #8B0000, #B22222); }
.stat-icon.tone-gold  { background: linear-gradient(135deg, #B8860B, #D4AF37); }
.stat-icon.tone-green { background: linear-gradient(135deg, #389E0D, #52C41A); }
.stat-icon.tone-cyan  { background: linear-gradient(135deg, #00838F, #00ACC1); }

/* 数字与标签 */
.stat-body { flex: 1; min-width: 0; }
.stat-value {
  font-size: 30px;
  font-weight: 700;
  color: var(--swu-text);
  line-height: 1.15;
  font-variant-numeric: tabular-nums;
  font-family: "Inter", ui-sans-serif, system-ui, sans-serif;
  letter-spacing: -0.03em;
}
.stat-label {
  margin-top: 4px;
  font-size: 13px;
  color: var(--swu-text-3);
  font-weight: 500;
}
.stat-hint {
  margin-top: 2px;
  font-size: 11px;
  color: var(--swu-text-3);
  opacity: 0.8;
}

/* 趋势箭头 */
.stat-delta {
  display: inline-flex; align-items: center; gap: 3px;
  margin-top: 6px;
  font-size: 12px; font-weight: 600;
}
.stat-delta.up   { color: var(--swu-success); }
.stat-delta.down { color: var(--swu-danger); }
.delta-arrow { font-size: 11px; }
</style>
