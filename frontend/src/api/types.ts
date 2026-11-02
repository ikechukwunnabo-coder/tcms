export type RoleCode =
  | "system_admin"
  | "admin"
  | "front_desk"
  | "medic"
  | "training_coordinator"
  | "accounts"
  | "due_diligence"
  | "md"
  | "printer"
  | "instructor"
  | "reports"
  | "verification";

export interface StaffUser {
  id: number;
  username: string;
  first_name: string;
  last_name: string;
  email: string;
  is_active: boolean;
  is_staff: boolean;
  role_codes: RoleCode[];
  roles: number[];
}

export interface LoginResponse {
  user: StaffUser;
  roles: RoleCode[];
  token: string;
}

export interface Role {
  id: number;
  code: RoleCode;
  name: string;
}

export interface Paginated<T> {
  data: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface LearnerContact {
  id: number;
  learner: number;
  contact_type: number | null;
  value: string;
  is_primary: boolean;
}

export interface LearnerDocument {
  id: number;
  learner: number;
  kind: string;
  object_key: string;
  mime: string;
  size_bytes: number;
  uploaded_at: string;
  uploaded_by: number | null;
  verified_at: string | null;
}

export interface Learner {
  id: number;
  badge_no: string;
  surname: string;
  first_name: string;
  middle_name: string;
  sex: "M" | "F" | "";
  birth_date: string | null;
  nationality: number | null;
  state: number | null;
  position: number | null;
  company: number | null;
  title: number | null;
  active: boolean;
  pertype: string;
  full_name: string;
  contacts: LearnerContact[];
  documents: LearnerDocument[];
}

export interface Company {
  id: number;
  agencode: string;
  name: string;
  email: string;
  active: boolean;
  is_individual: boolean;
}

export interface Nationality {
  id: number;
  natcode: string;
  country: string;
  nationality: string;
}

export interface State {
  id: number;
  code: string;
  name: string;
}

export interface Position {
  id: number;
  posicode: string;
  name: string;
}

export interface Title {
  id: number;
  name: string;
}

export interface ContactType {
  id: number;
  name: string;
}

export interface Course {
  id: number;
  course_code: string;
  name: string;
  cert_type: number | null;
  expiry_type: number;
  duration_days: number | null;
  validity_years: number | null;
  id_card: boolean;
  foet_required: boolean;
  opito_reg_code: string;
  refresher_course: string | null;
  active: boolean;
}

export interface Venue {
  id: number;
  name: string;
  address: string;
  capacity: number | null;
  active: boolean;
}

export interface Instructor {
  id: number;
  full_name: string;
  user: number | null;
  active: boolean;
}

export type SessionStatus = "scheduled" | "open" | "full" | "running" | "closed";

export interface CourseSession {
  id: number;
  course: number;
  course_name: string;
  course_code: string;
  venue: number | null;
  start_date: string;
  end_date: string | null;
  capacity: number | null;
  seats_taken: number;
  seats_available: number | null;
  reserve_pct: number;
  status: SessionStatus;
  created_at: string;
}

export type BookingState =
  | "registered"
  | "payment_uploaded"
  | "payment_rejected"
  | "confirmed"
  | "session_transferred"
  | "overflow"
  | "cancelled"
  | "attended"
  | "no_show"
  | "denied";

export interface Enrolment {
  id: number;
  learner: number;
  learner_name: string;
  badge_no: string;
  course: number;
  course_code: string;
  requested_session: number | null;
  session: number | null;
  original_session: number | null;
  session_start: string | null;
  granted_start: string | null;
  status: string;
  state: BookingState;
  booking_ref: string | null;
  seat_allocated_at: string | null;
  payment_verified_at: string | null;
  created_at: string;
}

export interface TrainingItem {
  id: number;
  training_record: number;
  course_item: number;
  passed: boolean | null;
  score: string | null;
}

export interface TrainingRecord {
  id: number;
  learner: number;
  learner_name: string;
  badge_no: string;
  course: number;
  course_code: string;
  session: number | null;
  enrolment: number | null;
  start_date: string | null;
  end_date: string | null;
  prev_expiry: string | null;
  status: number;
  status_code: string;
  reject_reason: string;
  instructor: string;
  items: TrainingItem[];
  created_at: string;
  updated_at: string;
}

export interface Certificate {
  id: number;
  training_record: number;
  learner: number;
  learner_name: string;
  badge_no: string;
  course_code: string;
  certificate_no: string;
  format: number | null;
  issued_at: string | null;
  issued_by: number | null;
  printed_at: string | null;
  printed_by: number | null;
  id_issued_at: string | null;
  id_printed_at: string | null;
  expiry_date: string | null;
  object_key: string;
  md_approved_by: number | null;
  md_approved_at: string | null;
  signature_applied: boolean;
  seal_applied: boolean;
  signature_object_key: string;
  seal_object_key: string;
  voided_at: string | null;
  void_reason: string;
  released_at: string | null;
  renewed_by_certificate: number | null;
  batch: number | null;
}

export type InvoiceStatus = "draft" | "issued" | "part_paid" | "paid" | "void";

export interface InvoiceLine {
  id: number;
  description: string;
  quantity: string;
  unit_price: string;
  amount: string;
}

export interface Invoice {
  id: number;
  invoice_no: string;
  corporate_account: number | null;
  corporate_account_name: string;
  enrolment: number | null;
  learner: number | null;
  learner_name: string;
  issue_date: string;
  due_date: string | null;
  currency: string;
  subtotal: string;
  tax: string;
  total: string;
  amount_paid: string;
  balance: string;
  status: InvoiceStatus;
  notes: string;
  lines: InvoiceLine[];
}

export type PaymentStatus = "pending" | "confirmed" | "failed" | "refunded";

export interface Payment {
  id: number;
  invoice: number;
  invoice_no: string;
  payment_ref: string;
  amount: string;
  paid_at: string;
  method: string;
  status: PaymentStatus;
  received_by: number | null;
  notes: string;
}

export interface CorporateAccount {
  id: number;
  name: string;
  company: number | null;
  lead_user: number | null;
  lead_email: string;
  credit_limit: string | null;
  terms_days: number;
  balance: string;
  active: boolean;
  nominee_count: number;
}

export type Fitness = "fit" | "fit_with_restrictions" | "unfit" | "";

export interface Medical {
  id: number;
  learner: number;
  learner_name: string;
  badge_no: string;
  record_no: string;
  issued_date: string | null;
  expiry_date: string | null;
  systolic: number | null;
  diastolic: number | null;
  fitness: Fitness;
  active: boolean;
  document: number | null;
  created_at: string;
}

export interface WorkflowStatus {
  id: number;
  code: string;
  name: string;
  next_role: number | null;
  terminal: boolean;
}

export interface Approval {
  id: number;
  training_record: number;
  current_status: number;
  step_no: number;
  assigned_role: number | null;
  action: string;
  reason: string;
  acted_by: number | null;
  acted_at: string | null;
  created_at: string;
}

export interface WorkflowCount {
  status: number;
  code: string;
  name: string;
  count: number;
  terminal: boolean;
  next_role: number | null;
}

export interface Dashboard {
  generated_at: string;
  as_of: string;
  kpis: {
    learners_total: number;
    learners_active: number;
    sessions_upcoming: number;
    enrolments_pending: number;
    certificates_issued: number;
    certificates_expiring_90d: number;
    invoices_outstanding_count: number;
    invoices_outstanding_total: string;
    revenue_collected_90d: string;
    medicals_expiring_30d: number;
    workflow_open: number;
  };
  workflow: WorkflowCount[];
  my_stages: Omit<WorkflowCount, "terminal">[];
  trend: {
    month: string;
    enrolments: number;
    certificates: number;
    revenue: string;
  }[];
  course_mix: {
    course_id: number;
    code: string;
    name: string;
    sessions: number;
    enrolments: number;
  }[];
  upcoming_sessions: {
    id: number;
    course_code: string;
    course_name: string;
    venue: string;
    start_date: string;
    end_date: string;
    capacity: number | null;
    seats_taken: number;
    status: string;
  }[];
  work_queue: {
    pending_enrolments: {
      id: number;
      booking_ref: string | null;
      learner: string;
      badge_no: string;
      course_code: string;
      start_date: string;
      state: BookingState;
      created_at: string;
    }[];
    unpaid_invoices: {
      id: number;
      invoice_no: string;
      issue_date: string;
      due_date: string;
      currency: string;
      balance: string;
      status: InvoiceStatus;
    }[];
    certificates_awaiting_release: {
      id: number;
      certificate_no: string;
      learner: string;
      issued_at: string;
      expiry_date: string;
      md_approved: boolean;
    }[];
  };
}

export interface ReportDef {
  id: number;
  code: string;
  name: string;
  roles: number[];
  sql_view: string;
}
