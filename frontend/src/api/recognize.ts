import { request } from "./http";
import type { RecognizeOut } from "./types";

export const recognizeApi = {
  recognizeImage(gateId: number, image: Blob) {
    const form = new FormData();
    form.append("image", image, "capture.jpg");
    return request<RecognizeOut>({
      url: "/recognize",
      method: "POST",
      params: { gate_id: gateId },
      data: form,
      headers: { "Content-Type": "multipart/form-data" },
      timeout: 30_000,
    });
  },
};
