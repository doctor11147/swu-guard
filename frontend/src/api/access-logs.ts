import { request } from "./http";
import type { AccessLogOut, Page } from "./types";

export interface LogQuery {
  from?: string;
  to?: string;
  decision?: string;
  person_id?: number;
  gate_id?: number;
  page?: number;
  page_size?: number;
}

export const logsApi = {
  list(params: LogQuery = {}) {
    return request<Page<AccessLogOut>>({
      url: "/access-logs",
      method: "GET",
      params,
    });
  },
  get(id: number) {
    return request<AccessLogOut>({ url: `/access-logs/${id}`, method: "GET" });
  },
  stats() {
    return request<{
      by_day: Array<Record<string, unknown>>;
      by_hour: Array<{ hour: string; total: number }>;
      by_gate: Array<{ gate_id: number; gate_name: string; total: number }>;
      by_decision: Record<string, number>;
      today_total: number;
      week_total: number;
    }>({ url: "/access-logs/stats", method: "GET" });
  },
  exportCsvUrl(params: LogQuery = {}): string {
    const qs = new URLSearchParams(
      Object.entries(params).filter(([, v]) => v !== undefined) as [string, string][],
    ).toString();
    return `/api/access-logs/export.csv${qs ? `?${qs}` : ""}`;
  },
};
