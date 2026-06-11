import { request } from "./http";
import type { Page, PersonOut } from "./types";

export interface PersonQuery {
  q?: string;
  role?: string;
  status?: string;
  college_id?: number;
  faculty_id?: number;
  campus?: string;
  dorm_zone?: string;
  enrollment_year?: number;
  page?: number;
  page_size?: number;
}

export interface FaceRegisterSummary {
  added: number;
  skipped_duplicates: number;
  skipped_no_face: number;
  skipped_spoof: number;
  skipped_quality: number;
}

export const personsApi = {
  list(params: PersonQuery = {}) {
    return request<Page<PersonOut>>({ url: "/persons", method: "GET", params });
  },
  get(id: number) {
    return request<PersonOut>({ url: `/persons/${id}`, method: "GET" });
  },
  create(data: Record<string, unknown>) {
    return request<PersonOut>({ url: "/persons", method: "POST", data });
  },
  update(id: number, data: Record<string, unknown>) {
    return request<PersonOut>({ url: `/persons/${id}`, method: "PUT", data });
  },
  remove(id: number) {
    return request<{ ok: boolean }>({ url: `/persons/${id}`, method: "DELETE" });
  },
  parseId(externalId: string) {
    return request<{
      valid: boolean;
      type_code?: string;
      type_name?: string;
      enrollment_year?: number;
      college_code?: string;
    }>({ url: `/persons/parse-id/${externalId}`, method: "GET" });
  },
  // 注册人脸（摄像头帧 / 上传照片，统一走后端多图 multipart 入库）
  addFaces(personId: number, files: File[]) {
    const fd = new FormData();
    for (const f of files) fd.append("images", f);
    return request<FaceRegisterSummary>({
      url: `/persons/${personId}/faces`,
      method: "POST",
      data: fd,
      headers: { "Content-Type": "multipart/form-data" },
      timeout: 60_000,
    });
  },
  listFaces(personId: number) {
    return request<Array<Record<string, unknown>>>({
      url: `/persons/${personId}/faces`,
      method: "GET",
    });
  },
};
