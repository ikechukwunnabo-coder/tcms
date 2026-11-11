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
  full_name: string;
  email: string;
  is_active: boolean;
  is_staff: boolean;
  role_codes: RoleCode[];
  roles: number[];
}

export interface UserRoleAssignment {
  id: number;
  user: number;
  role: number;
  name: string;
  code: RoleCode;
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
  vantage_id: string;
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
  front_id_text: string;
  back_id_text: string;
  refresher_course: string | null;
  active: boolean;
}

export interface CourseModule {
  id: number;
  name: string;
  active: boolean;
}

export interface CourseItem {
  id: number;
  name: string;
  active: boolean;
}

export interface CourseModuleRelation {
  id: number;
  course: number;
  module: number;
  name: string;
}

export interface CourseItemRelation {
  id: number;
  course: number;
  item: number;
  name: string;
}

export interface CertificateType {
  id: number;
  name: string;
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

export interface DocumentRecord {
  id: number;
  kind: string;
  owner_type: string;
  owner_id: number | null;
  object_key: string;
  mime: string;
  size_bytes: number;
  sha256: string;
  generated_at: string;
  generated_by: number | null;
}

export interface TrainingInstructor {
  id: number;
  training_record: number;
  instructor: number;
  module: number | null;
  module_name: string;
  training_date: string | null;
}

export interface DailyMedicalCheck {
  id: number;
  training_record: number;
  check_date: string;
  systolic: number | null;
  diastolic: number | null;
  notes: string;
  created_at: string;
  created_by: number | null;
}

export interface TrainingRecord {
  id: number;
  learner: number;
  learner_name: string;
  badge_no: string;
  company_name: string;
  course: number;
  course_name: string;
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
  foet_scan: number | null;
  payment_proof: number | null;
  welcome_letter: number | null;
  items: TrainingItem[];
  training_instructors: TrainingInstructor[];
  medical_checks: DailyMedicalCheck[];
  created_at: string;
  updated_at: string;
}

export interface ApprovalHistory {
  id: number;
  training_record: number;
  status: number;
  full_name: string;
  updated_at: string;
}

export interface JoiningInstruction {
  id: number;
  enrolment: number;
  session_id: number | null;
  version: number;
  is_current: boolean;
  delivery_status: string;
  sent_to: string;
  sent_at: string | null;
  issued_at: string;
  payload: Record<string, unknown>;
}

export interface TrainingWorkspace extends TrainingRecord {
  learner_detail: Learner;
  course_detail: Course;
  status_detail: WorkflowStatus;
  foet_scan_document: DocumentRecord | null;
  payment_proof_document: DocumentRecord | null;
  welcome_letter_document: DocumentRecord | null;
  medicals: Medical[];
  certificates: Certificate[];
  id_cards: IDCard[];
  status_history: ApprovalHistory[];
  joining_instruction: JoiningInstruction | null;
}

export interface MyActivity {
  pending: TrainingRecord[];
  recent: {
    id: number;
    training_record: number;
    record: TrainingRecord;
    action: string;
    reason: string;
    acted_at: string | null;
  }[];
}

export interface BulkActionResult {
  results: {
    id: number;
    ok: boolean;
    status?: number;
    code?: string;
    error?: string;
  }[];
  succeeded: number;
  failed: number;
}

export interface Certificate {
  id: number;
  training_record: number;
  learner: number;
  learner_name: string;
  badge_no: string;
  course_code: string;
  course_id_card: boolean;
  certificate_no: string;
  format: number | null;
  source: "generated" | "uploaded";
  opito_learner_id: string;
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

export interface CertificateVerification {
  is_valid: boolean;
  status: string;
  certificate_no: string;
  full_name: string;
  course: string;
  issued: string | null;
  expiry: string | null;
}

export interface IDCard {
  id: number;
  learner: number;
  learner_name: string;
  training_record: number;
  course_code: string;
  card_no: string;
  printed_at: string | null;
  printed_by: number | null;
  object_key: string;
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

export interface ReportYearRange {
  min: number;
  max: number;
  default: number;
}

export interface TrainingRecordReportRow {
  row_num: number;
  id: number;
  first_name: string;
  last_name: string;
  badge_no: string;
  birth_date: string;
  company: string;
  course: string;
  course_code: string;
  start: string;
  end: string;
  expiry: string;
  days: number | "";
  certificate: string;
}

export interface CourseMonthRow {
  c: number;
  course: string;
  course_code: string;
  month: string;
  month_no: number;
  value: number;
  course_total?: number;
}

export interface DelegateMonthRow {
  month: string;
  month_no: number;
  value: number;
}

export interface CourseTypeRow {
  type: string;
  course: string;
  count: number;
}

export interface RoleActivityRow {
  id: number;
  user_id: number | null;
  user: string;
  training_record: number;
  badge_no: string;
  learner: string;
  course: string;
  step: string;
  action: string;
  completed: string;
}

export interface RoleActivitySummaryRow {
  user_id: number | null;
  username: string;
  name: string;
  count: number;
}

export interface RoleOption {
  id: number;
  code: string;
  name: string;
}

export interface OpitoMonthlyRow {
  id: number;
  course: string;
  course_code: string;
  opito_reg_code: string;
  learner: string;
  badge_no: string;
  opito_learner_id: string;
  start: string;
  end: string;
  completed: string;
}

export interface FlowStatusRow {
  id: number;
  status: number;
  code: string;
  name: string;
  count: number;
  terminal: boolean;
  level: "terminal" | "critical" | "backlog" | "normal";
  next_role: number | null;
  next_role_name: string;
}

export interface FlowStatusReport {
  data: FlowStatusRow[];
  total: number;
  summary: {
    active_records: number;
    terminal_records: number;
    backlog_records: number;
    critical_records: number;
    backlog_stages: number;
    critical_stages: number;
  };
  thresholds: {
    backlog: number;
    critical: number;
  };
  next_roles: {
    role: number;
    name: string;
    count: number;
    stages: string[];
  }[];
}

export interface OpitoCohort {
  id: string;
  name: string;
  course: number;
  course_code: string;
  product_code: string;
  start: string;
  start_date: string;
  learners: number;
  record_count: number;
  object_key: string;
  file_name: string;
  fileName: string;
  file_id: number | null;
  generated_at: string | null;
}

export interface OpitoFileResult {
  id: number;
  course: number;
  course_code: string;
  product_code: string;
  start_date: string;
  record_count: number;
  object_key: string;
  file_name: string;
  fileName: string;
  generated_at: string | null;
  download_url: string;
  created_at: string;
  updated_at: string;
}

export interface OpitoMissingVantage {
  learnerId: number;
  fullName: string;
  badge: string;
}

export interface BackupResult {
  file_name: string;
  bytes: number;
  created_at: string;
}

export interface BackupTestResult {
  status: string;
  message: string;
  free_bytes: number;
  checked_at: string;
}
