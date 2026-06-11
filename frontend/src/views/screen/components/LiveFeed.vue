<script setup lang="ts">
import { useAutoAnimate } from "@formkit/auto-animate/vue";
import { usePreferredReducedMotion } from "@vueuse/core";
import { computed, watch } from "vue";

import type { AccessDecision, DashboardOut } from "@/api/types";

const props = defineProps<{
  logs: DashboardOut["recent_logs"];
  labels: Record<AccessDecision, string>;
}>();

const motion = usePreferredReducedMotion();
const [listRef, setAutoAnimate] = useAutoAnimate<HTMLDivElement>({
  duration: 280,
  easing: "cubic-bezier(0.22, 1, 0.36, 1)",
});

watch(
  () => motion.value,
  (value) => setAutoAnimate(value !== "reduce"),
  { immediate: true },
);

const rows = computed(() => (props.logs ?? []).slice(0, 9));

function formatTime(ts: string) {
  return ts.replace("T", " ").slice(11, 19) || "--:--:--";
}

function scoreText(score: number | null) {
  return score == null ? "--" : score.toFixed(2);
}
</script>

<template>
  <div class="live-feed">
    <div ref="listRef" class="live-feed__list">
      <article
        v-for="log in rows"
        :key="log.id"
        :class="['live-feed__row', `live-feed__row--${log.decision}`]"
      >
        <div class="live-feed__time">{{ formatTime(log.ts) }}</div>
        <div class="live-feed__main">
          <div class="live-feed__name">
            {{ log.person_name || '未识别人员' }}
            <span>{{ log.person_external_id || 'NO-ID' }}</span>
          </div>
          <div class="live-feed__gate">{{ log.gate_name || '未知门禁' }} · score {{ scoreText(log.score) }}</div>
        </div>
        <div :class="['live-feed__tag', `live-feed__tag--${log.decision}`]">
          {{ labels[log.decision] }}
        </div>
      </article>
      <div v-if="rows.length === 0" key="empty" class="live-feed__empty">暂无实时事件</div>
    </div>
  </div>
</template>

<style scoped>
.live-feed {
  width: 100%;
  height: 100%;
  min-height: 0;
  overflow: hidden;
}

.live-feed__list {
  display: flex;
  height: 100%;
  min-height: 0;
  flex-direction: column;
  gap: 10px;
  overflow: hidden;
}

.live-feed__row {
  display: grid;
  grid-template-columns: 78px minmax(0, 1fr) 82px;
  align-items: center;
  gap: 12px;
  min-height: 58px;
  padding: 10px 12px;
  border: 1px solid rgba(39, 216, 255, 0.12);
  border-left: 3px solid rgba(39, 216, 255, 0.55);
  border-radius: 12px;
  background: linear-gradient(90deg, rgba(39, 216, 255, 0.09), rgba(0, 61, 122, 0.08));
}

.live-feed__row--granted { border-left-color: #20c36b; }
.live-feed__row--rejected { border-left-color: #f97316; }
.live-feed__row--spoof { border-left-color: #b22222; }
.live-feed__row--no_face { border-left-color: #64748b; }

.live-feed__time {
  color: #27d8ff;
  font-family: "DIN Alternate", monospace;
  font-size: 17px;
  font-weight: 800;
  letter-spacing: 0.06em;
}

.live-feed__main {
  min-width: 0;
}

.live-feed__name {
  overflow: hidden;
  color: #eaf4ff;
  font-size: 16px;
  font-weight: 800;
  letter-spacing: 0.04em;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.live-feed__name span {
  margin-left: 8px;
  color: #8aa8c7;
  font-size: 12px;
  font-weight: 600;
}

.live-feed__gate {
  margin-top: 5px;
  overflow: hidden;
  color: #8aa8c7;
  font-size: 12px;
  letter-spacing: 0.05em;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.live-feed__tag {
  justify-self: end;
  min-width: 70px;
  padding: 6px 10px;
  border-radius: 999px;
  text-align: center;
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.08em;
}

.live-feed__tag--granted { background: rgba(32, 195, 107, 0.14); color: #20c36b; }
.live-feed__tag--rejected { background: rgba(249, 115, 22, 0.16); color: #f97316; }
.live-feed__tag--spoof { background: rgba(178, 34, 34, 0.18); color: #ff6b6b; }
.live-feed__tag--no_face { background: rgba(100, 116, 139, 0.18); color: #94a3b8; }

.live-feed__empty {
  display: grid;
  flex: 1;
  place-items: center;
  color: #8aa8c7;
  font-size: 16px;
  letter-spacing: 0.12em;
}
</style>
