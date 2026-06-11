import type { InjectionKey, Ref } from "vue";

export interface GateFocusState {
  activeGateNo: Ref<number | null>;
  focusGate: (gateNo: number) => void;
  scheduleHide: () => void;
  clearHide: () => void;
}

export const gateFocusKey: InjectionKey<GateFocusState> = Symbol("gateFocus");

export function useGateFocus(): GateFocusState {
  const activeGateNo = ref<number | null>(null);
  let hideTimer: number | null = null;

  function clearHide() {
    if (hideTimer) {
      window.clearTimeout(hideTimer);
      hideTimer = null;
    }
  }

  function focusGate(gateNo: number) {
    clearHide();
    activeGateNo.value = gateNo;
  }

  function scheduleHide() {
    clearHide();
    hideTimer = window.setTimeout(() => {
      activeGateNo.value = null;
    }, 200);
  }

  onBeforeUnmount(clearHide);

  return { activeGateNo, focusGate, scheduleHide, clearHide };
}
