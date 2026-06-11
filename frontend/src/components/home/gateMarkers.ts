import type { GateOut } from "@/api/types";

export const MAP_W = 2048;
export const MAP_H = 1448;

export interface GateMarker {
  gateNo: number;
  cx: number;
  cy: number;
  r: number;
  image: string;
}

export interface BoundGateMarker extends GateMarker {
  gate: GateOut | null;
}

export type GateStatusTone = "active" | "maintenance" | "disabled";

export function gateStatusLabel(status?: GateOut["status"]): string {
  return ({
    online: "在线",
    offline: "维护",
    disabled: "停用",
  } as Record<string, string>)[status || ""] || "未登记";
}

export function gateStatusTone(status?: GateOut["status"]): GateStatusTone {
  if (status === "online") return "active";
  if (status === "offline") return "maintenance";
  return "disabled";
}

export function gateStatusClass(status?: GateOut["status"]): string {
  return `is-${gateStatusTone(status)}`;
}

export const MARKERS: GateMarker[] = [
  { gateNo: 1, cx: 1437, cy: 974, r: 36, image: "/gates/gate-1.jpg" },
  { gateNo: 2, cx: 720, cy: 1329, r: 37, image: "/gates/gate-2.jpg" },
  { gateNo: 3, cx: 1232, cy: 1050, r: 43, image: "/gates/gate-3.jpg" },
  { gateNo: 5, cx: 1985, cy: 526, r: 35, image: "/gates/gate-5.jpg" },
  { gateNo: 6, cx: 235, cy: 1253, r: 42, image: "/gates/gate-6.jpg" },
  { gateNo: 7, cx: 1712, cy: 144, r: 42, image: "/gates/gate-7.jpg" },
  { gateNo: 8, cx: 54, cy: 1038, r: 50, image: "/gates/gate-8.jpg" },
];

/**
 * 门标记和后端门数据的唯一绑定入口。
 *
 * 绑定规则：从 GateOut.code + GateOut.name 提取第一个数字，作为真实门号；
 * 地图标记只按 gateNo 匹配，不按数组顺序或数据库 id 推断。这样数据库 id
 * 即使是 1..7，也能正确绑定到“5号门/6号门/7号门/8号门”。
 */
export function extractGateNo(gate: GateOut): number {
  const raw = `${gate.code || ""} ${gate.name || ""}`;
  const match = raw.match(/\d+/);
  return match ? Number(match[0]) : gate.id;
}

export function bindGateMarkers(gates: GateOut[]): BoundGateMarker[] {
  const byNo = new Map<number, GateOut>();
  for (const gate of gates) {
    byNo.set(extractGateNo(gate), gate);
  }
  return MARKERS.map((marker) => ({
    ...marker,
    gate: byNo.get(marker.gateNo) ?? null,
  }));
}

export function listUnmarkedGates(gates: GateOut[]): GateOut[] {
  const markerNos = new Set(MARKERS.map((m) => m.gateNo));
  return gates.filter((gate) => !markerNos.has(extractGateNo(gate)));
}
