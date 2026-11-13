import type { RoleCode } from "../api/types";

export interface RoleManual {
  file: string;
  role: RoleCode;
  title: string;
  summary: string;
  duties: string[];
  controls: string[];
  escalation: string;
}

export const ROLE_MANUALS: Record<RoleCode, RoleManual> = {
  system_admin: {
    file: "01-sys-admin.html",
    role: "system_admin",
    title: "System administrator",
    summary:
      "Own the console configuration, staff access model, reference data and operational continuity.",
    duties: [
      "Create staff accounts, assign roles and deactivate leavers promptly.",
      "Maintain courses, modules, items, reference data and certificate configuration.",
      "Review audit activity and recover or export data when operations require it.",
      "Run backups before major configuration or bulk workflow changes.",
    ],
    controls: [
      "System administrators bypass role filters, so every change is attributed in the audit trail.",
      "Use the least-privilege role for new staff and review access after team changes.",
      "Never share tokens or account credentials between users.",
    ],
    escalation: "Escalate suspected account compromise or data loss to the managing director immediately.",
  },
  admin: {
    file: "02-admin.html",
    role: "admin",
    title: "Administrator",
    summary:
      "Coordinate day-to-day training administration across learners, scheduling, certification and billing.",
    duties: [
      "Set up learners, courses, sessions and enrolments.",
      "Monitor pending tasks and unblock workflow transitions.",
      "Oversee certificate release, billing exceptions and reporting follow-up.",
      "Keep learner and corporate records complete before certification.",
    ],
    controls: [
      "Release certificates only after signing and payment checks are satisfied.",
      "Record clear reasons when cancelling, rejecting or reversing a workflow step.",
      "Use reports and the activity trail to verify actions taken by the team.",
    ],
    escalation: "Escalate policy exceptions, credit issues or unresolved disputes to the managing director.",
  },
  front_desk: {
    file: "04-front-desk.html",
    role: "front_desk",
    title: "Front desk",
    summary:
      "Receive learners, confirm bookings and keep enrolment and attendance records accurate.",
    duties: [
      "Register learners and capture complete contact and identification details.",
      "Create and confirm enrolments for scheduled sessions.",
      "Check learner documents, medicals and pre-course requirements.",
      "Update attendance and hand completed records to certification.",
    ],
    controls: [
      "Verify identity before changing learner records or releasing documents.",
      "Do not confirm a booking without an available seat and required payment state.",
      "Route medical or eligibility concerns to the medic or coordinator.",
    ],
    escalation: "Escalate eligibility, safeguarding or payment disputes to the training coordinator or administrator.",
  },
  medic: {
    file: "05-medic.html",
    role: "medic",
    title: "Medic",
    summary:
      "Assess fitness, record medical observations and protect the medical gate on training and certification.",
    duties: [
      "Record medical examinations, outcomes and expiry dates.",
      "Capture daily blood-pressure observations where the course requires them.",
      "Mark learners fit, unfit or temporarily restricted with a clear reason.",
      "Review expiring medicals before course delivery.",
    ],
    controls: [
      "Never certify fitness outside your professional competence or scope.",
      "Medical outcomes override commercial pressure; record the clinical basis for restrictions.",
      "Keep medical information confidential and share only on a need-to-know basis.",
    ],
    escalation: "Escalate emergency clinical events through the centre emergency procedure and notify the administrator.",
  },
  training_coordinator: {
    file: "06-training-coordinator.html",
    role: "training_coordinator",
    title: "Training coordinator",
    summary:
      "Plan course delivery, allocate instructors and resources, and move training records through certification.",
    duties: [
      "Schedule sessions, venues, instructors and supporting resources.",
      "Confirm enrolments, manage capacity and resolve scheduling conflicts.",
      "Capture delivery evidence, instructor assignments, modules and items.",
      "Trigger and monitor certification, ID cards and OPITO file preparation.",
    ],
    controls: [
      "Do not exceed session capacity or bypass the medical and payment gates.",
      "Record delivery changes and reasons in the workflow trail.",
      "Validate OPITO Vantage IDs before generating the upload file.",
    ],
    escalation: "Escalate resource shortages, failed deliveries or disputed attendance to the administrator.",
  },
  accounts: {
    file: "07-accounts.html",
    role: "accounts",
    title: "Accounts",
    summary:
      "Manage invoices, payments, corporate accounts and billing evidence for training delivery.",
    duties: [
      "Raise invoices and record payments against the correct learner or corporate account.",
      "Maintain payment references, proof of payment and outstanding balances.",
      "Resolve billing exceptions and reconcile payment files.",
      "Provide billing status to coordinators without disclosing unrelated financial data.",
    ],
    controls: [
      "Never alter payment evidence or invoice totals without an audit reason.",
      "Respect corporate credit limits and segregation-of-duties controls.",
      "Do not release certification for unpaid or blocked accounts without approval.",
    ],
    escalation: "Escalate credit breaches, duplicate payments or suspected fraud to the managing director.",
  },
  due_diligence: {
    file: "08-due-diligence.html",
    role: "due_diligence",
    title: "Due diligence",
    summary:
      "Verify learner and corporate records before training, certification or commercial commitments.",
    duties: [
      "Review learner identity, documentation and corporate relationships.",
      "Check sanctions, eligibility and record completeness where required.",
      "Record findings and flag discrepancies before approval.",
      "Support audit and compliance reviews with traceable evidence.",
    ],
    controls: [
      "Keep findings factual, attributable and free from unsupported conclusions.",
      "Do not disclose sensitive checks outside the authorised review group.",
      "Escalate conflicts of interest immediately.",
    ],
    escalation: "Escalate adverse findings or integrity concerns to the managing director.",
  },
  md: {
    file: "09-md.html",
    role: "md",
    title: "Managing director",
    summary:
      "Approve high-risk commercial and certification decisions and monitor centre performance.",
    duties: [
      "Review reporting intelligence, workflow backlog and operational risk.",
      "Approve exceptions that require executive authority.",
      "Sign or authorise certificate release where the policy requires it.",
      "Hold administrators accountable for control and data quality.",
    ],
    controls: [
      "Maintain separation between approval and operational execution where possible.",
      "Require documented reasons for exceptions and overrides.",
      "Use current reports rather than informal extracts for decisions.",
    ],
    escalation: "Escalate legal, regulatory or safeguarding matters through the centre's governance process.",
  },
  printer: {
    file: "10-printer.html",
    role: "printer",
    title: "Printer",
    summary:
      "Produce and control physical certificates and ID cards from approved digital records.",
    duties: [
      "Print only certificates and ID cards that are released or otherwise authorised.",
      "Mark documents as printed and keep print runs traceable.",
      "Check document quality before handing finished items to the front desk.",
      "Report damaged or mismatched print runs for correction.",
    ],
    controls: [
      "Do not alter certificate data or issue unapproved documents.",
      "Secure blank stock and prevent unauthorised reproduction.",
      "Reconcile every print run against the certificate or ID-card register.",
    ],
    escalation: "Escalate unauthorised document requests, stock discrepancies or quality failures to the administrator.",
  },
  hr_manager: {
    file: "13-hr-manager.html",
    role: "hr_manager",
    title: "HR Manager",
    summary:
      "Own employee records, pay setup, time approval and workforce reporting while protecting sensitive payroll data.",
    duties: [
      "Create and maintain employee records, positions and employment status.",
      "Maintain bank details, salaries, allowances and deductions within your authority.",
      "Review and approve submitted timesheets, then resolve rejected time entries.",
      "Prepare leave and provision records and read payslips for employee queries.",
      "Coordinate HR changes with finance before they affect a live pay run.",
    ],
    controls: [
      "Change pay and bank details only with documented employee authorisation.",
      "Never share salaries, bank details or payslips with staff outside an authorised HR or finance role.",
      "Do not approve your own timesheet or a timesheet you prepared.",
      "Keep the reason for every pay or bank-detail correction in the audit trail.",
    ],
    escalation:
      "Escalate disputed pay, suspected fraud, data-protection incidents or pay runs requiring correction to the administrator and finance lead.",
  },
  hr_officer: {
    file: "14-hr-officer.html",
    role: "hr_officer",
    title: "HR Officer",
    summary:
      "Maintain non-sensitive employee records and timekeeping while respecting payroll confidentiality.",
    duties: [
      "Create and update employee contact and employment details within the approved fields.",
      "Maintain positions and link employees to the correct learner and user records.",
      "Record and submit timesheets for approval, correcting rejected entries promptly.",
      "Refer salary, bank, payslip and provision questions to the HR manager.",
    ],
    controls: [
      "Never ask colleagues to reveal salary, bank details, payslips or tax records.",
      "Do not attempt to approve timesheets or alter rates.",
      "Record only information required for HR administration and keep it accurate.",
      "Report accidental exposure of payroll information immediately.",
    ],
    escalation:
      "Escalate payroll questions, data-protection concerns and timesheet disputes to the HR manager.",
  },
  instructor: {
    file: "11-instructor.html",
    role: "instructor",
    title: "Instructor",
    summary:
      "Deliver training, record attendance and provide the evidence needed to certify learners.",
    duties: [
      "Confirm assigned sessions, learners and delivery resources.",
      "Record attendance, assessments and delivery evidence accurately.",
      "Report absent, unfit or withdrawn learners promptly.",
      "Hand complete delivery records to the training coordinator.",
    ],
    controls: [
      "Do not certify attendance or competence you did not observe.",
      "Follow the approved course content and safety procedures.",
      "Record incidents and delivery deviations in the workflow trail.",
    ],
    escalation: "Escalate safety incidents, learner misconduct or resource failures to the training coordinator.",
  },
  reports: {
    file: "12-reports.html",
    role: "reports",
    title: "Reporting",
    summary:
      "Produce, validate and explain operational reports for management and compliance.",
    duties: [
      "Run the reporting index and verify filters, year ranges and dataset scope.",
      "Export CSV, XLSX or PDF only from the approved report endpoints.",
      "Reconcile OPITO and certification reports against operational records.",
      "Explain trends, anomalies and data-quality issues to management.",
    ],
    controls: [
      "Do not edit source records to make a report reconcile; correct the record through the proper workflow.",
      "Protect exported files according to their sensitivity.",
      "State the reporting period and filters whenever presenting results.",
    ],
    escalation: "Escalate suspected data corruption or reporting-control failures to the administrator.",
  },
  verification: {
    file: "03-verification.html",
    role: "verification",
    title: "Verification",
    summary:
      "Respond to certificate verification requests and confirm record authenticity against the live register.",
    duties: [
      "Verify certificate numbers and learner records using the public verification page or console register.",
      "Report validity, status, course and relevant dates without disclosing medical or payment data.",
      "Record suspicious or altered documents and refer them for investigation.",
      "Guide requestors to the public verification route where appropriate.",
    ],
    controls: [
      "Never confirm a document that is void, expired or not present in the register.",
      "Do not share personal data beyond what verification requires.",
      "Keep verification enquiries traceable when an exception is investigated.",
    ],
    escalation: "Escalate forged, altered or contested certificates to the administrator and managing director.",
  },
};

export function manualForRole(role: RoleCode): RoleManual {
  return ROLE_MANUALS[role];
}

export function manualForFile(file: string): RoleManual | undefined {
  return Object.values(ROLE_MANUALS).find((manual) => manual.file === file);
}
