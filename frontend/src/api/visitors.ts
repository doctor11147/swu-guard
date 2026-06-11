import { request } from "./http";
import type { Page } from "./types";

export interface VisitorRegisterPayload {
  id_card: string;
  name: string;
  phone?: string;
  email?: string;
  note?: string;
}

export interface VisitorRegisterOut {
  person_id: number;
  id_card: string;
  name: string;
  status: string;
  created: boolean;
}

export interface VisitorFaceRegisterOut {
  person_id: number;
  id_card: string;
  added: number;
  skipped_duplicates: number;
  skipped_no_face: number;
  skipped_spoof: number;
  skipped_quality: number;
}

export interface AppointmentCreatePayload {
  id_card: string;
  visit_reason: string;
  arrival_date: string;
  departure_date: string;
  arrival_slot: number;
  departure_slot: number;
}

export interface AppointmentOut {
  id: number;
  person_id: number;
  id_card: string;
  visitor_name: string;
  visit_reason: string;
  arrival_slot: number;
  departure_slot: number;
  appointment_date: string;
  arrival_date: string;
  departure_date: string;
  status: "pending" | "approved" | "rejected" | "expired" | "cancelled";
  reviewed_by: number | null;
  reviewed_at: string | null;
  reject_reason: string | null;
  created_at: string;
  updated_at: string;
}

export interface AppointmentQuery {
  status?: AppointmentOut["status"] | "";
  date?: string;
  person_id?: number;
  page?: number;
  page_size?: number;
}

export interface AppointmentReviewPayload {
  action: "approve" | "reject";
  reason?: string;
}

export const visitorsApi = {
  register(data: VisitorRegisterPayload) {
    return request<VisitorRegisterOut>({
      url: "/visitors/register",
      method: "POST",
      data,
    });
  },
  registerFaces(idCard: string, images: File[]) {
    const form = new FormData();
    images.forEach((image) => form.append("images", image));
    return request<VisitorFaceRegisterOut>({
      url: "/visitors/faces",
      method: "POST",
      params: { id_card: idCard },
      data: form,
      headers: { "Content-Type": "multipart/form-data" },
      timeout: 60_000,
    });
  },
  createAppointment(data: AppointmentCreatePayload) {
    return request<AppointmentOut>({
      url: "/visitors/appointments",
      method: "POST",
      data,
    });
  },
  lookup(idCard: string) {
    return request<Page<AppointmentOut>>({
      url: "/visitors/appointments/lookup",
      method: "POST",
      data: { id_card: idCard },
    });
  },
  listAppointments(params: AppointmentQuery) {
    return request<Page<AppointmentOut>>({
      url: "/visitors/appointments",
      method: "GET",
      params,
    });
  },
  reviewAppointment(id: number, data: AppointmentReviewPayload) {
    return request<AppointmentOut>({
      url: `/visitors/appointments/${id}/review`,
      method: "PUT",
      data,
    });
  },
  cancelAppointment(id: number) {
    return request<AppointmentOut>({
      url: `/visitors/appointments/${id}/cancel`,
      method: "PUT",
    });
  },
};
