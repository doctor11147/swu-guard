import { computed, onBeforeUnmount, ref, shallowRef, type Ref } from "vue";

import { CameraUnavailableError, closeCamera, openCamera } from "@/utils/camera";

export type CameraFacingMode = "user" | "environment";

export interface UseCameraStreamOptions {
  facingMode?: CameraFacingMode;
  width?: number;
  height?: number;
}

export function useCameraStream(options: UseCameraStreamOptions = {}) {
  const videoRef = ref<HTMLVideoElement>();
  const stream = shallowRef<MediaStream | null>(null);
  const cameraError = ref("");
  const starting = ref(false);
  const ready = ref(false);
  const facingMode = ref<CameraFacingMode>(options.facingMode ?? "user");
  const captureCanvas = document.createElement("canvas");

  const mirrored = computed(() => facingMode.value === "user");
  const cameraOk = computed(() => !!stream.value && ready.value && !cameraError.value);
  const sourceSize = computed(() => ({
    width: videoRef.value?.videoWidth || options.width || 1280,
    height: videoRef.value?.videoHeight || options.height || 720,
  }));

  async function start() {
    if (starting.value || stream.value) return;
    cameraError.value = "";
    ready.value = false;
    starting.value = true;
    try {
      const media = await openCamera({
        video: {
          facingMode: facingMode.value,
          width: { ideal: options.width ?? 1280 },
          height: { ideal: options.height ?? 720 },
        },
        audio: false,
      });
      stream.value = media;
      if (videoRef.value) {
        videoRef.value.srcObject = media;
        await videoRef.value.play();
        ready.value = true;
      }
    } catch (e: unknown) {
      cameraError.value = e instanceof CameraUnavailableError || e instanceof Error
        ? e.message
        : String(e);
      stop();
    } finally {
      starting.value = false;
    }
  }

  function stop() {
    closeCamera(stream.value);
    stream.value = null;
    ready.value = false;
    if (videoRef.value) {
      videoRef.value.pause();
      videoRef.value.srcObject = null;
    }
  }

  async function retry() {
    stop();
    await start();
  }

  function captureDataUrl(quality = 0.62): string | null {
    const video = videoRef.value;
    if (!video || !video.videoWidth || !video.videoHeight) return null;
    captureCanvas.width = video.videoWidth;
    captureCanvas.height = video.videoHeight;
    const ctx = captureCanvas.getContext("2d");
    if (!ctx) return null;
    ctx.drawImage(video, 0, 0, captureCanvas.width, captureCanvas.height);
    return captureCanvas.toDataURL("image/jpeg", quality);
  }

  function captureBlob(quality = 0.9): Promise<Blob | null> {
    const video = videoRef.value;
    if (!video || !video.videoWidth || !video.videoHeight) return Promise.resolve(null);
    captureCanvas.width = video.videoWidth;
    captureCanvas.height = video.videoHeight;
    const ctx = captureCanvas.getContext("2d");
    if (!ctx) return Promise.resolve(null);
    ctx.drawImage(video, 0, 0, captureCanvas.width, captureCanvas.height);
    return new Promise((resolve) => captureCanvas.toBlob(resolve, "image/jpeg", quality));
  }

  onBeforeUnmount(stop);

  return {
    videoRef: videoRef as Ref<HTMLVideoElement | undefined>,
    stream,
    cameraError,
    starting,
    ready,
    cameraOk,
    mirrored,
    facingMode,
    sourceSize,
    start,
    stop,
    retry,
    captureDataUrl,
    captureBlob,
  };
}
