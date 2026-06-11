export const motionDurations = {
  snap: 0.18,
  fast: 0.28,
  base: 0.42,
  slow: 0.72,
  result: 2.5,
  cooldown: 1.5,
} as const;

export const motionEase = {
  standard: "power3.out",
  entrance: "back.out(1.35)",
  precise: "power2.inOut",
  alert: "elastic.out(1, 0.55)",
} as const;

export const swuMotionColors = {
  primary: "#003D7A",
  danger: "#B22222",
  gold: "#D4AF37",
  granted: "#20C36B",
  rejected: "#F97316",
  spoof: "#EF4444",
  network: "#94A3B8",
  glass: "rgba(9, 30, 66, 0.58)",
} as const;

export const screenMotion = {
  designWidth: 1920,
  designHeight: 1080,
  refreshMs: 15_000,
  chartDuration: 900,
  pulseDuration: 1.8,
  resizeDebounceMs: 180,
} as const;

export const screenPalette = {
  bgStart: "#00142B",
  bgMid: "#001B3D",
  bgEnd: "#020A18",
  panel: "rgba(5, 25, 55, 0.76)",
  panelStrong: "rgba(0, 61, 122, 0.34)",
  line: "rgba(69, 180, 255, 0.38)",
  cyan: "#27D8FF",
  cyanSoft: "rgba(39, 216, 255, 0.18)",
  text: "#EAF4FF",
  textMuted: "#8AA8C7",
  success: "#20C36B",
  warning: "#F97316",
  danger: "#B22222",
  gold: "#D4AF37",
} as const;
