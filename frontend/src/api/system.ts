import { request } from "./http";
import type {
  CollegeOut,
  ConfigOut,
  DashboardOut,
  FacultyOut,
} from "./types";

export const systemApi = {
  faculties() {
    return request<FacultyOut[]>({ url: "/system/faculties", method: "GET" });
  },
  colleges(params: { faculty_id?: number; q?: string; active?: boolean } = {}) {
    return request<CollegeOut[]>({ url: "/system/colleges", method: "GET", params });
  },
  configs() {
    return request<ConfigOut[]>({ url: "/system/configs", method: "GET" });
  },
  getConfig(key: string) {
    return request<ConfigOut>({ url: `/system/configs/${key}`, method: "GET" });
  },
  setConfig(key: string, value: unknown) {
    return request<ConfigOut>({
      url: `/system/configs/${key}`,
      method: "PUT",
      data: { value },
    });
  },
  dashboard() {
    return request<DashboardOut>({ url: "/system/dashboard", method: "GET" });
  },
};
