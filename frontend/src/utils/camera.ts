/**
 * 摄像头工具：兼容旧 API + secure-context 防御 + 友好错误提示。
 *
 * 浏览器只在 secure context（HTTPS 或 hostname=localhost）下暴露
 * ``navigator.mediaDevices``。访问 http://127.0.0.1 或局域网 IP 会返回 undefined。
 */

/** 返回当前页面是否是 secure context（getUserMedia 可用）。 */
export function isSecureContextForMedia(): boolean {
  if (typeof window === "undefined") return false;
  if (window.isSecureContext) return true;
  // 兜底：localhost / 127.0.0.1 / ::1 也算 secure
  const h = location.hostname;
  return h === "localhost" || h === "127.0.0.1" || h === "::1";
}

/** 获取兼容的 getUserMedia（含 legacy 浏览器前缀回退）。
 *  注意：TS 类型上 ``navigator.mediaDevices`` 永远存在，但实际在
 *  非 secure context（http + 非 localhost）下浏览器会让它整个 undefined。
 *  所以必须用宽松的类型断言来真正运行时判存。 */
function getMediaDevicesShim(): MediaDevices | null {
  const nav = navigator as Navigator & {
    mediaDevices?: MediaDevices;
    getUserMedia?: (
      c: MediaStreamConstraints,
      ok: (s: MediaStream) => void,
      err: (e: unknown) => void,
    ) => void;
    webkitGetUserMedia?: typeof nav.getUserMedia;
    mozGetUserMedia?: typeof nav.getUserMedia;
  };

  // 现代 API
  if (nav.mediaDevices && typeof nav.mediaDevices.getUserMedia === "function") {
    return nav.mediaDevices;
  }

  // legacy: 老旧浏览器仅暴露 navigator.getUserMedia / webkitGetUserMedia
  const legacy = nav.getUserMedia || nav.webkitGetUserMedia || nav.mozGetUserMedia;
  if (!legacy) return null;

  return {
    getUserMedia(c: MediaStreamConstraints): Promise<MediaStream> {
      return new Promise((resolve, reject) =>
        legacy.call(nav, c, resolve, reject),
      );
    },
  } as unknown as MediaDevices;
}

export class CameraUnavailableError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "CameraUnavailableError";
  }
}

/**
 * 打开摄像头。失败时抛出带有清晰中文消息的错误。
 *
 * @throws CameraUnavailableError 当 secure-context 不满足或浏览器不支持
 */
export async function openCamera(
  constraints: MediaStreamConstraints = {
    video: { width: { ideal: 1280 }, height: { ideal: 720 } },
    audio: false,
  },
): Promise<MediaStream> {
  if (!isSecureContextForMedia()) {
    throw new CameraUnavailableError(
      "浏览器禁止在非 HTTPS / 非 localhost 页面访问摄像头。" +
      "请用 http://localhost:5173 打开（不要用 127.0.0.1 或 IP）。",
    );
  }
  const md = getMediaDevicesShim();
  if (!md) {
    throw new CameraUnavailableError(
      "当前浏览器不支持 getUserMedia。请用 Chrome / Edge / Safari 最新版。",
    );
  }
  try {
    return await md.getUserMedia(constraints);
  } catch (e: unknown) {
    const err = e as DOMException;
    if (err.name === "NotAllowedError" || err.name === "PermissionDeniedError") {
      throw new CameraUnavailableError("已被拒绝授权摄像头，请在浏览器地址栏图标里重新允许。");
    }
    if (err.name === "NotFoundError" || err.name === "DevicesNotFoundError") {
      throw new CameraUnavailableError("找不到摄像头设备。");
    }
    if (err.name === "NotReadableError" || err.name === "TrackStartError") {
      throw new CameraUnavailableError("摄像头被其他程序占用，请关闭后重试。");
    }
    throw new CameraUnavailableError(`摄像头打开失败：${err.message || err.name || String(e)}`);
  }
}

/** 停止所有 track 并释放设备。 */
export function closeCamera(stream: MediaStream | null | undefined): void {
  stream?.getTracks().forEach((t) => t.stop());
}
