/**
 * 后端契约（与 docs/api_spec.md 同步）。
 * 暂手写；P7+ 可改用 openapi-typescript 自动生成。
 */
export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export type AdminRole = "superadmin" | "admin" | "guard" | "viewer";

export interface AdminOut {
  id: number;
  username: string;
  name: string;
  email: string | null;
  role: AdminRole;
  is_active: boolean;
  last_login_at: string | null;
  created_at: string;
  /** 仅 role='guard' 时非空；其它角色全权限。 */
  gate_ids: number[];
}

export interface TokenOut {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_at: string;
  user: AdminOut;
}

export type PersonRole = "student" | "graduate" | "teacher" | "staff" | "visitor";
export type PersonStatus = "active" | "suspended" | "graduated" | "expired";
export type Campus = "beibei" | "rongchang";
export type DormZone = "nan" | "zhu" | "mei" | "li" | "ju" | "tao" | "xing";

export interface PersonOut {
  id: number;
  external_id: string;
  name: string;
  role: PersonRole;
  college_id: number | null;
  faculty_name: string | null;
  school_name: string | null;
  major: string | null;
  class_code: string | null;
  enrollment_year: number | null;
  campus: Campus;
  dorm_zone: DormZone | null;
  phone: string | null;
  email: string | null;
  status: PersonStatus;
  note: string | null;
  created_at: string;
  updated_at: string;
  embedding_count: number;
}

export interface FacultyOut {
  id: number;
  code: string;
  name: string;
  is_active: boolean;
  colleges_count?: number;
}

export interface CollegeOut {
  id: number;
  faculty_id: number | null;
  code: string;
  name: string;
  short_name: string | null;
  is_active: boolean;
}

export interface GateOut {
  id: number;
  code: string;
  name: string;
  campus: Campus;
  location: string | null;
  direction: "in" | "out" | "both";
  ip_address: string | null;
  status: "online" | "offline" | "disabled";
  note: string | null;
  created_at: string;
  updated_at: string;
}

export type AccessDecision = "granted" | "rejected" | "spoof" | "no_face";
export type PublicRecognizeDecision = "granted" | "denied" | "no_match" | "spoof" | "network";

export interface RecognizeMatchOut {
  person_id?: number;
  student_id?: string;
  name?: string;
  score?: number;
  detail?: string;
  visitor_appointment_id?: number;
}

export interface RecognizeFaceOut {
  bbox?: number[];
  score?: number;
  spoof_score?: number | null;
  is_real?: boolean | null;
  quality_score?: number | null;
  quality_adjusted_threshold?: number | null;
  kps?: number[] | number[][] | null;
  keypoints?: number[] | number[][] | null;
  landmarks?: number[] | number[][] | null;
  runtime_thresholds?: Record<string, unknown> | null;
  decision: "granted" | "rejected" | "spoof" | "no_face";
  match: RecognizeMatchOut | null;
  detail?: string;
  visitor_appointment_id?: number | null;
}

export interface RecognizeOut {
  faces: RecognizeFaceOut[];
  threshold: number;
  gate_id?: number | null;
  timing?: Record<string, number>;
  runtime_thresholds?: Record<string, unknown> | null;
}

export interface AccessLogOut {
  id: number;
  ts: string;
  gate_id: number | null;
  matched_person_id: number | null;
  visitor_appointment_id: number | null;
  score: number | null;
  spoof_score: number | null;
  decision: AccessDecision;
  snapshot_path: string | null;
  detail: string | null;
  gate_name: string | null;
  person_name: string | null;
  person_external_id: string | null;
}

export interface ConfigOut {
  config_key: string;
  value_json: { value: unknown };
  description: string | null;
  updated_at: string;
}

export interface DashboardOut {
  school: { name_zh?: string; motto?: string; spirit?: string; founded_year?: number };
  today: { total: number; granted: number; rejected: number; spoof: number; no_face: number };
  week: { total: number; granted: number; rejected: number; spoof: number; no_face: number };
  gates_online: number;
  gates_total: number;
  persons_total: number;
  persons_active: number;
  embedding_total: number;
  recent_logs: Array<{
    id: number;
    ts: string;
    decision: AccessDecision;
    score: number | null;
    spoof_score: number | null;
    gate_name: string | null;
    person_name: string | null;
    person_external_id: string | null;
  }>;
  by_decision_pie: Array<{ name: string; value: number }>;
  by_hour_line: Array<{ hour: string; total: number }>;
  by_faculty_bar: Array<{ faculty: string; total: number }>;
}
