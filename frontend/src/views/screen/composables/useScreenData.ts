import { computed, onActivated, onBeforeUnmount, onDeactivated, onMounted, ref } from "vue";

import { gatesApi } from "@/api/gates";
import { systemApi } from "@/api/system";
import type { AccessDecision, DashboardOut, GateOut } from "@/api/types";
import { screenMotion } from "@/styles/motion-tokens";

const decisionLabel: Record<AccessDecision, string> = {
  granted: "通行",
  rejected: "未识别",
  spoof: "活体拒",
  no_face: "无脸",
};

const gateStatusLabel: Record<GateOut["status"], string> = {
  online: "在线",
  offline: "离线",
  disabled: "停用",
};

function emptyCounter() {
  return { total: 0, granted: 0, rejected: 0, spoof: 0, no_face: 0 };
}

function createEmptyDashboard(): DashboardOut {
  return {
    school: { name_zh: "西南大学" },
    today: emptyCounter(),
    week: emptyCounter(),
    gates_online: 0,
    gates_total: 0,
    persons_total: 0,
    persons_active: 0,
    embedding_total: 0,
    recent_logs: [],
    by_decision_pie: [],
    by_hour_line: [],
    by_faculty_bar: [],
  };
}

function normalizeDashboard(next?: DashboardOut | null): DashboardOut {
  const base = createEmptyDashboard();
  if (!next) return base;
  const maybeFas = (next as DashboardOut & { fas_distribution?: DashboardOut["by_decision_pie"] }).fas_distribution;

  return {
    ...base,
    ...next,
    school: { ...base.school, ...(next.school ?? {}) },
    today: { ...base.today, ...(next.today ?? {}) },
    week: { ...base.week, ...(next.week ?? {}) },
    recent_logs: next.recent_logs ?? [],
    by_decision_pie: next.by_decision_pie ?? maybeFas ?? [],
    by_hour_line: next.by_hour_line ?? [],
    by_faculty_bar: next.by_faculty_bar ?? [],
  };
}

function formatClock(date: Date) {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
}

export function useScreenData() {
  const dashboard = ref<DashboardOut>(createEmptyDashboard());
  const gates = ref<GateOut[]>([]);
  const clock = ref(new Date());
  const loading = ref(false);
  const error = ref<string | null>(null);
  const lastUpdated = ref<Date | null>(null);

  let clockTimer: number | null = null;
  let refreshTimer: number | null = null;
  let pending = false;

  async function load() {
    if (pending) return;
    pending = true;
    loading.value = true;
    try {
      const [dashboardRes, gateRes] = await Promise.all([
        systemApi.dashboard(),
        gatesApi.list(),
      ]);
      dashboard.value = normalizeDashboard(dashboardRes);
      gates.value = gateRes ?? [];
      error.value = null;
      lastUpdated.value = new Date();
    } catch (err) {
      error.value = err instanceof Error ? err.message : "数据刷新失败";
    } finally {
      loading.value = false;
      pending = false;
    }
  }

  function start() {
    if (clockTimer === null) {
      clockTimer = window.setInterval(() => {
        clock.value = new Date();
      }, 1000);
    }
    if (refreshTimer === null) {
      void load();
      refreshTimer = window.setInterval(() => void load(), screenMotion.refreshMs);
    }
  }

  function stop() {
    if (clockTimer !== null) {
      clearInterval(clockTimer);
      clockTimer = null;
    }
    if (refreshTimer !== null) {
      clearInterval(refreshTimer);
      refreshTimer = null;
    }
  }

  onMounted(start);
  onActivated(start);
  onDeactivated(stop);
  onBeforeUnmount(stop);

  const gateStats = computed(() => {
    const byList = gates.value.reduce(
      (acc, gate) => {
        acc[gate.status] += 1;
        return acc;
      },
      { online: 0, offline: 0, disabled: 0 } as Record<GateOut["status"], number>,
    );
    const total = dashboard.value.gates_total || gates.value.length;
    const online = dashboard.value.gates_online || byList.online;
    return {
      total,
      online,
      offline: byList.offline,
      disabled: byList.disabled,
    };
  });

  const successRate = computed(() => {
    const today = dashboard.value.today;
    if (!today.total) return 0;
    return Math.round((today.granted / today.total) * 1000) / 10;
  });

  const kpiCards = computed(() => [
    {
      key: "today-total",
      title: "今日通行总数",
      value: dashboard.value.today.total,
      suffix: "",
      subtitle: `通过 ${dashboard.value.today.granted} · 拒绝 ${dashboard.value.today.rejected}`,
      tone: "primary" as const,
      icon: "PASS",
    },
    {
      key: "gates-online",
      title: "在线门禁数",
      value: gateStats.value.online,
      suffix: " / " + gateStats.value.total,
      subtitle: `离线 ${gateStats.value.offline} · 停用 ${gateStats.value.disabled}`,
      tone: "success" as const,
      icon: "GATE",
    },
    {
      key: "spoof-blocked",
      title: "异常 · 活体拦截",
      value: dashboard.value.today.spoof,
      suffix: "",
      subtitle: `本周异常 ${dashboard.value.week.spoof}`,
      tone: "danger" as const,
      icon: "FAS",
    },
    {
      key: "success-rate",
      title: "识别成功率",
      value: successRate.value,
      suffix: "%",
      subtitle: `注册 ${dashboard.value.persons_active}/${dashboard.value.persons_total}`,
      tone: "gold" as const,
      icon: "AI",
      decimals: 1,
    },
  ]);

  const rankRows = computed(() => dashboard.value.by_faculty_bar.slice(0, 10));
  const trendRows = computed(() => dashboard.value.by_hour_line);
  const decisionRows = computed(() => dashboard.value.by_decision_pie);
  const recentLogs = computed(() => dashboard.value.recent_logs.slice(0, 10));
  const clockText = computed(() => formatClock(clock.value));
  const lastUpdatedText = computed(() => (lastUpdated.value ? formatClock(lastUpdated.value).slice(11) : "--:--:--"));

  return {
    dashboard,
    gates,
    loading,
    error,
    clock,
    clockText,
    lastUpdatedText,
    gateStats,
    kpiCards,
    trendRows,
    rankRows,
    decisionRows,
    recentLogs,
    decisionLabel,
    gateStatusLabel,
    load,
    start,
    stop,
  };
}
