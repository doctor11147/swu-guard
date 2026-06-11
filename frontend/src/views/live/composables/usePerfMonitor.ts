import { computed, onActivated, onBeforeUnmount, onDeactivated, onMounted, readonly, ref } from "vue";

export interface LatencySample {
  seq: number;
  ts: number;
  latency: number;
}

interface PerfMonitorOptions {
  sampleSize?: number;
  fpsWindowMs?: number;
  idleDecayMs?: number;
  idleZeroMs?: number;
}

type FrameId = number | string;

const DEFAULT_OPTIONS = {
  sampleSize: 60,
  fpsWindowMs: 5000,
  idleDecayMs: 1000,
  idleZeroMs: 3000,
} as const;

function nowMs() {
  return typeof performance !== "undefined" && performance.now ? performance.now() : Date.now();
}

function round(value: number, digits = 1) {
  const base = 10 ** digits;
  return Math.round(value * base) / base;
}

function percentile(values: number[], ratio: number) {
  if (!values.length) return null;
  const sorted = [...values].sort((a, b) => a - b);
  const index = Math.min(sorted.length - 1, Math.max(0, Math.ceil(sorted.length * ratio) - 1));
  return sorted[index];
}

export function usePerfMonitor(options: PerfMonitorOptions = {}) {
  const resolved = { ...DEFAULT_OPTIONS, ...options };
  const samples = ref<LatencySample[]>([]);
  const responseTimes = ref<number[]>([]);
  const lastResponseAt = ref<number | null>(null);
  const ticker = ref(nowMs());

  const pendingById = new Map<FrameId, number>();
  let pendingAnonymous: number | null = null;
  let seq = 0;
  let timer: number | null = null;

  function pruneResponses(now = nowMs()) {
    responseTimes.value = responseTimes.value.filter((ts) => now - ts <= resolved.fpsWindowMs);
  }

  function recordLatency(sentAt: number, receivedAt: number) {
    const latency = receivedAt - sentAt;
    if (!Number.isFinite(latency) || latency < 0 || latency > 60_000) return;
    samples.value = [
      ...samples.value,
      { seq: ++seq, ts: receivedAt, latency: round(latency, 1) },
    ].slice(-resolved.sampleSize);
  }

  function markSent(id?: FrameId) {
    try {
      const ts = nowMs();
      if (id === undefined || id === null) {
        pendingAnonymous = ts;
      } else {
        pendingById.set(id, ts);
      }
    } catch {
      // 旁路观测失败时必须静默，不影响识别主流程。
    }
  }

  function markReceived(id?: FrameId) {
    try {
      const ts = nowMs();
      lastResponseAt.value = ts;
      responseTimes.value = [...responseTimes.value, ts];
      pruneResponses(ts);

      let sentAt: number | undefined;
      if (id !== undefined && id !== null) {
        sentAt = pendingById.get(id);
        pendingById.delete(id);
      } else if (pendingAnonymous !== null) {
        sentAt = pendingAnonymous;
        pendingAnonymous = null;
      }

      if (sentAt != null) recordLatency(sentAt, ts);
    } catch {
      // 旁路观测失败时必须静默，不影响识别主流程。
    }
  }

  function reset() {
    try {
      samples.value = [];
      responseTimes.value = [];
      lastResponseAt.value = null;
      ticker.value = nowMs();
      pendingById.clear();
      pendingAnonymous = null;
      seq = 0;
    } catch {
      // no-op
    }
  }

  function startTicker() {
    if (timer !== null) return;
    timer = window.setInterval(() => {
      const ts = nowMs();
      ticker.value = ts;
      pruneResponses(ts);
    }, 500);
  }

  function stopTicker() {
    if (timer === null) return;
    clearInterval(timer);
    timer = null;
  }

  onMounted(startTicker);
  onActivated(startTicker);
  onDeactivated(stopTicker);
  onBeforeUnmount(stopTicker);

  const stats = computed(() => {
    const latencies = samples.value.map((item) => item.latency);
    if (!latencies.length) {
      return { current: null, avg: null, min: null, max: null, p95: null, count: 0 };
    }
    const sum = latencies.reduce((acc, item) => acc + item, 0);
    return {
      current: latencies.at(-1) ?? null,
      avg: round(sum / latencies.length, 1),
      min: round(Math.min(...latencies), 1),
      max: round(Math.max(...latencies), 1),
      p95: round(percentile(latencies, 0.95) ?? 0, 1),
      count: latencies.length,
    };
  });

  const fps = computed(() => {
    const last = lastResponseAt.value;
    const current = ticker.value;
    if (!last) return 0;
    const idleMs = current - last;
    if (idleMs >= resolved.idleZeroMs) return 0;

    const times = responseTimes.value.filter((ts) => current - ts <= resolved.fpsWindowMs);
    if (times.length < 2) return idleMs > resolved.idleDecayMs ? 0 : 1;

    const span = Math.max(1, times[times.length - 1] - times[0]);
    const rawFps = ((times.length - 1) * 1000) / span;
    const decay = idleMs <= resolved.idleDecayMs
      ? 1
      : Math.max(0, 1 - (idleMs - resolved.idleDecayMs) / (resolved.idleZeroMs - resolved.idleDecayMs));
    return round(rawFps * decay, 1);
  });

  const active = computed(() => fps.value > 0 || samples.value.length > 0);

  return {
    samples: readonly(samples),
    stats,
    fps,
    active,
    markSent,
    markReceived,
    reset,
  };
}

export type PerfMonitor = ReturnType<typeof usePerfMonitor>;
