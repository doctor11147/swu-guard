import { request } from "./http";

export interface RuntimeThresholds {
  det_thresh: number;
  spoof_thresh: number;
  match_thresh: number;
  quality_thresh: number;
  consensus_frames: number;
}

export interface RuntimeRecognitionConfig {
  profile: string;
  det_thresh: number;
  spoof_thresh: number;
  match_thresh: number;
  quality_thresh: number;
  consensus_frames: number;
  manual_review: boolean;
  auto_grant_enabled: boolean;
  reason: string;
}

export interface AdaptiveState {
  enabled: boolean;
  mode: "off" | "rule_only" | "vlm" | "vlm_weather";
  profile: string;
  risk_level: "low" | "medium" | "high" | "critical";
  runtime_config: RuntimeRecognitionConfig | null;
  last_reason: string | null;
  expires_at: string | null;
  last_updated_at: string | null;
}

export const adaptiveApi = {
  state() {
    return request<AdaptiveState>({ url: "/adaptive/state", method: "GET" });
  },

  evaluate(gate_id?: number, use_weather = false, image_base64?: string) {
    return request({
      url: "/adaptive/evaluate",
      method: "POST",
      data: { gate_id, use_weather, image_base64 },
    });
  },

  apply() {
    return request({ url: "/adaptive/apply", method: "POST" });
  },

  updateConfig(payload: {
    enabled?: boolean;
    mode?: string;
    vlm_provider?: string;
    vlm_interval_seconds?: number;
    weather_enabled?: boolean;
  }) {
    return request({ url: "/adaptive/config", method: "PUT", data: payload });
  },

  snapshots() {
    return request({ url: "/adaptive/snapshots", method: "GET" });
  },

  policies() {
    return request({ url: "/adaptive/policies", method: "GET" });
  },
};
