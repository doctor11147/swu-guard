import { computed, onActivated, onBeforeUnmount, onDeactivated, onMounted, ref } from "vue";

import { screenMotion } from "@/styles/motion-tokens";

interface UseScreenScaleOptions {
  designWidth?: number;
  designHeight?: number;
}

export function useScreenScale(options: UseScreenScaleOptions = {}) {
  const designWidth = options.designWidth ?? screenMotion.designWidth;
  const designHeight = options.designHeight ?? screenMotion.designHeight;
  const scale = ref(1);
  const offsetX = ref(0);
  const offsetY = ref(0);
  const viewportWidth = ref(typeof window === "undefined" ? designWidth : window.innerWidth);
  const viewportHeight = ref(typeof window === "undefined" ? designHeight : window.innerHeight);

  let resizeTimer: number | null = null;
  let listening = false;
  let prevBodyMargin = "";
  let prevBodyOverflow = "";
  let prevBodyBackground = "";
  let bodyStylesApplied = false;

  function calcScale() {
    viewportWidth.value = window.innerWidth;
    viewportHeight.value = window.innerHeight;
    const nextScale = Math.min(window.innerWidth / designWidth, window.innerHeight / designHeight);
    scale.value = Number.isFinite(nextScale) && nextScale > 0 ? nextScale : 1;
    offsetX.value = (window.innerWidth - designWidth * scale.value) / 2;
    offsetY.value = (window.innerHeight - designHeight * scale.value) / 2;
  }

  function onResize() {
    if (resizeTimer !== null) clearTimeout(resizeTimer);
    resizeTimer = window.setTimeout(() => {
      calcScale();
      resizeTimer = null;
    }, screenMotion.resizeDebounceMs);
  }

  function applyPageOnlyBodyStyles() {
    if (bodyStylesApplied) return;
    prevBodyMargin = document.body.style.margin;
    prevBodyOverflow = document.body.style.overflow;
    prevBodyBackground = document.body.style.background;
    document.body.style.margin = "0";
    document.body.style.overflow = "hidden";
    document.body.style.background = "#00142B";
    bodyStylesApplied = true;
  }

  function restorePageOnlyBodyStyles() {
    if (!bodyStylesApplied) return;
    document.body.style.margin = prevBodyMargin;
    document.body.style.overflow = prevBodyOverflow;
    document.body.style.background = prevBodyBackground;
    bodyStylesApplied = false;
  }

  function start() {
    calcScale();
    if (!listening) {
      window.addEventListener("resize", onResize);
      listening = true;
    }
  }

  function stop() {
    if (resizeTimer !== null) {
      clearTimeout(resizeTimer);
      resizeTimer = null;
    }
    if (listening) {
      window.removeEventListener("resize", onResize);
      listening = false;
    }
  }

  function startPage() {
    applyPageOnlyBodyStyles();
    start();
  }

  function stopPage() {
    stop();
    restorePageOnlyBodyStyles();
  }

  onMounted(startPage);
  onActivated(startPage);
  onDeactivated(stopPage);
  onBeforeUnmount(() => {
    stopPage();
  });

  const screenStyle = computed(() => ({
    width: `${designWidth}px`,
    height: `${designHeight}px`,
    transform: `translate3d(${offsetX.value}px, ${offsetY.value}px, 0) scale(${scale.value})`,
  }));

  return {
    scale,
    viewportWidth,
    viewportHeight,
    screenStyle,
    calcScale,
  };
}
