import { computed, onBeforeUnmount, ref, unref, watch, type Ref } from "vue";

import { recognizeApi } from "@/api/recognize";
import type {
  AccessDecision,
  PublicRecognizeDecision,
  RecognizeFaceOut,
  RecognizeMatchOut,
  RecognizeOut,
} from "@/api/types";

export type GateRecognitionPhase =
  | "idle"
  | "detecting"
  | "verifying"
  | "result"
  | "cooldown"
  | "reconnecting"
  | "paused"
  | "error";

type MaybeRef<T> = T | Ref<T>;

export interface SourceSize {
  width: number;
  height: number;
}

export interface TrackedFace {
  bbox: [number, number, number, number];
  decision: AccessDecision;
  score: number;
  areaRatio: number;
  matchId: number | null;
  matchName: string;
  match: RecognizeMatchOut | null;
  spoofScore: number | null;
  isReal: boolean | null;
  qualityScore: number | null;
  qualityAdjustedThreshold: number | null;
  runtimeThresholds: Record<string, unknown> | null;
  kps: number[] | number[][] | null;
}

export interface GateRecognitionResult {
  decision: PublicRecognizeDecision;
  name: string;
  spoof: boolean;
  rawDecision: AccessDecision | "network";
}

export interface UseGateRecognitionOptions {
  gateId: MaybeRef<number | null | undefined>;
  gateCode: MaybeRef<string | null | undefined>;
  enabled: MaybeRef<boolean>;
  sourceSize: () => SourceSize;
  captureDataUrl: (quality?: number) => string | null;
  captureBlob: (quality?: number) => Promise<Blob | null>;
  onResult?: (result: GateRecognitionResult) => void;
}

const LOOP_INTERVAL_MS = 180;
const STABLE_MS = 620;
const RESULT_MS = 2500;
const COOLDOWN_MS = 1500;
const NO_FACE_RESET_MS = 900;
const MIN_FACE_AREA_RATIO = 0.075;
const LARGE_FACE_AREA_RATIO = 0.045;
const MAX_RECONNECT_MS = 5000;

function getWsUrl(): string {
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${proto}//${window.location.host}/api/ws/recognize`;
}

function normalizeBbox(raw?: number[]): [number, number, number, number] | null {
  if (!raw || raw.length < 4) return null;
  const [x1, y1, x2, y2] = raw.map((n) => Number(n));
  if (![x1, y1, x2, y2].every(Number.isFinite)) return null;
  if (x2 <= x1 || y2 <= y1) return null;
  return [x1, y1, x2, y2];
}

function finiteNumberOrNull(value: unknown): number | null {
  if (value == null) return null;
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : null;
}

function mapDecision(raw?: AccessDecision): PublicRecognizeDecision {
  if (raw === "granted") return "granted";
  if (raw === "spoof") return "spoof";
  if (raw === "no_face") return "no_match";
  return "denied";
}

function faceKey(face: TrackedFace | null): string | null {
  if (!face) return null;
  if (face.matchId != null) return `person:${face.matchId}`;
  return `decision:${face.decision}`;
}

function resultKey(face: RecognizeFaceOut | null | undefined, decision: PublicRecognizeDecision): string {
  const personId = face?.match?.person_id;
  if (personId != null) return `person:${personId}`;
  return `decision:${decision}`;
}

function toTrackedFace(face: RecognizeFaceOut, source: SourceSize): TrackedFace | null {
  const bbox = normalizeBbox(face.bbox);
  if (!bbox) return null;
  const [x1, y1, x2, y2] = bbox;
  const area = Math.max(0, x2 - x1) * Math.max(0, y2 - y1);
  const frameArea = Math.max(1, source.width * source.height);
  return {
    bbox,
    decision: face.decision,
    score: Number(face.score ?? 0),
    areaRatio: area / frameArea,
    matchId: face.match?.person_id ?? null,
    matchName: face.match?.name ?? "",
    match: face.match ? { ...face.match } : null,
    spoofScore: finiteNumberOrNull(face.spoof_score),
    isReal: face.is_real ?? null,
    qualityScore: finiteNumberOrNull(face.quality_score),
    qualityAdjustedThreshold: finiteNumberOrNull(face.quality_adjusted_threshold),
    runtimeThresholds: face.runtime_thresholds ?? null,
    kps: face.kps ?? face.keypoints ?? face.landmarks ?? null,
  };
}

function movementIsStable(prev: TrackedFace | null, next: TrackedFace, source: SourceSize): boolean {
  if (!prev) return false;
  const [ax1, ay1, ax2, ay2] = prev.bbox;
  const [bx1, by1, bx2, by2] = next.bbox;
  const acx = (ax1 + ax2) / 2;
  const acy = (ay1 + ay2) / 2;
  const bcx = (bx1 + bx2) / 2;
  const bcy = (by1 + by2) / 2;
  const centerDelta = Math.hypot((bcx - acx) / source.width, (bcy - acy) / source.height);
  const areaDelta = Math.abs(next.areaRatio - prev.areaRatio) / Math.max(next.areaRatio, prev.areaRatio, 0.001);
  return centerDelta < 0.045 && areaDelta < 0.32;
}

function pickMainFace(faces: RecognizeFaceOut[], source: SourceSize) {
  const tracked = faces
    .map((face) => toTrackedFace(face, source))
    .filter((face): face is TrackedFace => !!face)
    .sort((a, b) => b.areaRatio - a.areaRatio);
  return {
    main: tracked[0] ?? null,
    largeCount: tracked.filter((face) => face.areaRatio >= LARGE_FACE_AREA_RATIO).length,
  };
}

export function useGateRecognition(options: UseGateRecognitionOptions) {
  const phase = ref<GateRecognitionPhase>("idle");
  const wsStatus = ref<"closed" | "connecting" | "open" | "reconnecting">("closed");
  const primaryFace = ref<TrackedFace | null>(null);
  const threshold = ref(0.4);
  const fps = ref(0);
  const multipleFaces = ref(false);
  const tooFar = ref(false);
  const repeatBlocked = ref(false);
  const lastResult = ref<GateRecognitionResult | null>(null);

  let ws: WebSocket | null = null;
  let loopTimer: number | null = null;
  let reconnectTimer: number | null = null;
  let resultTimer: number | null = null;
  let cooldownTimer: number | null = null;
  let inflight = false;
  let running = false;
  let committing = false;
  let reconnectAttempt = 0;
  let stableSince: number | null = null;
  let previousFace: TrackedFace | null = null;
  let lastLoopAt = 0;
  let lastCommittedKey: string | null = null;
  let noFaceSince: number | null = null;

  const enabledValue = computed(() => Boolean(unref(options.enabled)));

  const statusText = computed(() => {
    if (!enabledValue.value) return "等待门禁与摄像头就绪";
    if (wsStatus.value === "connecting") return "连接识别服务中…";
    if (wsStatus.value === "reconnecting") return "识别服务重连中…";
    if (multipleFaces.value) return "请单人通行";
    if (repeatBlocked.value) return "已核验，请通过闸机";
    if (tooFar.value) return "请靠近摄像头";
    if (phase.value === "verifying") return "核验中…";
    if (phase.value === "result") return "核验完成";
    if (phase.value === "cooldown") return "请通过，系统即将复位";
    if (phase.value === "detecting") return "保持正对摄像头";
    if (phase.value === "paused") return "页面已暂停识别";
    if (phase.value === "error") return "识别服务异常";
    return "请正对摄像头";
  });

  function clearTimer(timer: number | null) {
    if (timer != null) window.clearTimeout(timer);
  }

  function resetStability() {
    stableSince = null;
    previousFace = null;
  }

  function clearFaceAfterAbsence() {
    const now = performance.now();
    if (noFaceSince == null) noFaceSince = now;
    if (now - noFaceSince >= NO_FACE_RESET_MS) {
      lastCommittedKey = null;
      repeatBlocked.value = false;
    }
  }

  function setResult(result: GateRecognitionResult) {
    lastResult.value = result;
    options.onResult?.(result);
    phase.value = "result";
    clearTimer(resultTimer);
    clearTimer(cooldownTimer);
    resultTimer = window.setTimeout(() => {
      phase.value = "cooldown";
      cooldownTimer = window.setTimeout(() => {
        if (phase.value === "cooldown") phase.value = "idle";
        resetStability();
      }, COOLDOWN_MS);
    }, RESULT_MS);
  }

  function setNetworkResult() {
    lastCommittedKey = "decision:network";
    setResult({ decision: "network", name: "", spoof: false, rawDecision: "network" });
  }

  async function commitVerification() {
    if (committing || phase.value === "result" || phase.value === "cooldown") return;
    const gateId = unref(options.gateId);
    if (!gateId) {
      setNetworkResult();
      return;
    }
    committing = true;
    phase.value = "verifying";
    resetStability();
    try {
      const blob = await options.captureBlob(0.9);
      if (!blob) {
        setNetworkResult();
        return;
      }
      const out: RecognizeOut = await recognizeApi.recognizeImage(gateId, blob);
      threshold.value = out.threshold ?? threshold.value;
      const face = out.faces?.[0];
      const verifiedFace = face ? toTrackedFace(face, options.sourceSize()) : null;
      if (verifiedFace) primaryFace.value = verifiedFace;
      const decision = mapDecision(face?.decision);
      const key = resultKey(face, decision);
      lastCommittedKey = key;
      repeatBlocked.value = false;
      setResult({
        decision,
        name: face?.match?.name ?? "",
        spoof: decision === "spoof",
        rawDecision: face?.decision ?? "network",
      });
    } catch {
      setNetworkResult();
    } finally {
      committing = false;
    }
  }

  function maybeAdvanceState(face: TrackedFace | null, largeCount: number) {
    if (phase.value === "result" || phase.value === "cooldown" || phase.value === "verifying") return;
    multipleFaces.value = largeCount > 1;
    if (!face) {
      primaryFace.value = null;
      tooFar.value = false;
      multipleFaces.value = false;
      if (phase.value !== "reconnecting") phase.value = "idle";
      resetStability();
      clearFaceAfterAbsence();
      return;
    }

    noFaceSince = null;
    primaryFace.value = face;
    tooFar.value = face.areaRatio < MIN_FACE_AREA_RATIO;
    if (multipleFaces.value || tooFar.value) {
      phase.value = "detecting";
      resetStability();
      return;
    }

    const key = faceKey(face);
    if (lastCommittedKey && key === lastCommittedKey) {
      repeatBlocked.value = true;
      phase.value = "idle";
      resetStability();
      return;
    }
    repeatBlocked.value = false;

    const source = options.sourceSize();
    const now = performance.now();
    const stable = movementIsStable(previousFace, face, source);
    if (!stable) stableSince = now;
    if (stableSince == null) stableSince = now;
    previousFace = face;
    phase.value = "detecting";
    if (now - stableSince >= STABLE_MS) {
      void commitVerification();
    }
  }

  function handleMessage(event: MessageEvent<string>) {
    inflight = false;
    let payload: { faces?: RecognizeFaceOut[]; threshold?: number; error?: string };
    try {
      payload = JSON.parse(event.data);
    } catch {
      return;
    }
    if (payload.error) {
      phase.value = "error";
      resetStability();
      return;
    }
    if (payload.threshold != null) threshold.value = payload.threshold;
    const source = options.sourceSize();
    const { main, largeCount } = pickMainFace(payload.faces ?? [], source);
    maybeAdvanceState(main, largeCount);
  }

  function stopLoop() {
    clearTimer(loopTimer);
    loopTimer = null;
    inflight = false;
  }

  function loop() {
    if (!running || !enabledValue.value) return;
    if (ws?.readyState === WebSocket.OPEN && !inflight) {
      const dataUrl = options.captureDataUrl(0.58);
      if (dataUrl) {
        ws.send(JSON.stringify({
          image: dataUrl,
          gate_code: unref(options.gateCode) || undefined,
        }));
        inflight = true;
        const now = performance.now();
        if (lastLoopAt) fps.value = Math.round(1000 / Math.max(1, now - lastLoopAt));
        lastLoopAt = now;
      }
    }
    loopTimer = window.setTimeout(loop, LOOP_INTERVAL_MS);
  }

  function cleanupSocket() {
    if (!ws) return;
    ws.onopen = null;
    ws.onmessage = null;
    ws.onerror = null;
    ws.onclose = null;
    if (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING) {
      ws.close();
    }
    ws = null;
  }

  function scheduleReconnect() {
    if (!running || !enabledValue.value) return;
    stopLoop();
    cleanupSocket();
    wsStatus.value = "reconnecting";
    phase.value = "reconnecting";
    reconnectAttempt += 1;
    const delay = Math.min(MAX_RECONNECT_MS, 500 * 2 ** Math.min(reconnectAttempt, 4));
    clearTimer(reconnectTimer);
    reconnectTimer = window.setTimeout(connect, delay);
  }

  function connect() {
    if (!running || !enabledValue.value || ws) return;
    wsStatus.value = reconnectAttempt > 0 ? "reconnecting" : "connecting";
    ws = new WebSocket(getWsUrl());
    ws.onopen = () => {
      wsStatus.value = "open";
      reconnectAttempt = 0;
      if (phase.value === "reconnecting" || phase.value === "error") phase.value = "idle";
      stopLoop();
      loop();
    };
    ws.onmessage = handleMessage;
    ws.onerror = scheduleReconnect;
    ws.onclose = scheduleReconnect;
  }

  function start() {
    if (running || !enabledValue.value) return;
    running = true;
    connect();
  }

  function pause() {
    running = false;
    wsStatus.value = "closed";
    phase.value = "paused";
    stopLoop();
    clearTimer(reconnectTimer);
    cleanupSocket();
    resetStability();
  }

  function resume() {
    if (!enabledValue.value) return;
    running = false;
    start();
  }

  function stop() {
    running = false;
    wsStatus.value = "closed";
    phase.value = "idle";
    stopLoop();
    clearTimer(reconnectTimer);
    clearTimer(resultTimer);
    clearTimer(cooldownTimer);
    cleanupSocket();
    resetStability();
    primaryFace.value = null;
  }

  function onVisibilityChange() {
    if (document.hidden) pause();
    else resume();
  }

  watch(enabledValue, (enabled) => {
    if (enabled) resume();
    else stop();
  }, { immediate: true });

  document.addEventListener("visibilitychange", onVisibilityChange);

  onBeforeUnmount(() => {
    document.removeEventListener("visibilitychange", onVisibilityChange);
    stop();
  });

  return {
    phase,
    wsStatus,
    primaryFace,
    threshold,
    fps,
    multipleFaces,
    tooFar,
    repeatBlocked,
    lastResult,
    statusText,
    start,
    pause,
    resume,
    stop,
  };
}
