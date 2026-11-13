import {
  Award,
  Bell,
  BookOpen,
  Building2,
  CalendarDays,
  ChartNoAxesCombined,
  ClipboardCheck,
  ClipboardList,
  Database,
  FileSpreadsheet,
  FileText,
  Files,
  GitBranch,
  Globe2,
  History,
  Landmark,
  ListChecks,
  LockKeyhole,
  MapPin,
  PlugZap,
  ReceiptText,
  ScrollText,
  ShieldCheck,
  Stethoscope,
  UserCog,
  Users,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import type { RoleCode } from "../api/types";
import {
  ADMIN_TOOLS_ROLES,
  BILLING_ROLES,
  CERTIFICATE_READ,
  FINANCE_ROLES,
  HR_MANAGER_ROLES,
  HR_ROLES,
  LEARNER_ROLES,
  MEDICAL_ROLES,
  REPORTING_ROLES,
  USER_ADMIN_ROLES,
} from "../auth/roles";

export interface AxisNavItem {
  title: string;
  description: string;
  to: string;
  icon: LucideIcon;
  roles: RoleCode[];
}

export interface AxisNavGroup {
  label: string;
  items: AxisNavItem[];
}

const TASK_ROLES: RoleCode[] = [
  "system_admin",
  "admin",
  "front_desk",
  "medic",
  "training_coordinator",
  "accounts",
  "due_diligence",
  "md",
  "printer",
  "instructor",
  "verification",
];

const OPITO_ROLES: RoleCode[] = ["system_admin", "printer"];

const CENTRE_ROLES: RoleCode[] = [
  "system_admin",
  "admin",
  "front_desk",
  "medic",
  "training_coordinator",
  "accounts",
  "due_diligence",
  "md",
  "printer",
  "instructor",
  "reports",
  "verification",
  "hr_manager",
  "hr_officer",
];

export const AXIS_GROUPS: AxisNavGroup[] = [
  {
    label: "Tasks",
    items: [
      {
        title: "My Pending Tasks",
        description:
          "Act on the pending tasks related to your role by approving, rejecting or updating training data.",
        to: "/tasks",
        icon: ClipboardCheck,
        roles: TASK_ROLES,
      },
      {
        title: "My Activity",
        description:
          "See your own training-workflow activity: which steps you've completed, and when.",
        to: "/activity",
        icon: History,
        roles: TASK_ROLES,
      },
    ],
  },
  {
    label: "Operations",
    items: [
      {
        title: "Opito Files",
        description:
          "Generate the CSV files that will be uploaded onto the OPITO official website for the generation of new certificates.",
        to: "/opito-files",
        icon: FileSpreadsheet,
        roles: OPITO_ROLES,
      },
      {
        title: "Manage Learners",
        description: "Add, modify and remove learners, and assign them to courses.",
        to: "/learners",
        icon: Users,
        roles: LEARNER_ROLES,
      },
      {
        title: "All Training Records",
        description: "Manage/view all existing training records in the database.",
        to: "/training-records",
        icon: ListChecks,
        roles: LEARNER_ROLES,
      },
    ],
  },
  {
    label: "People",
    items: [
      {
        title: "HR Workspace",
        description:
          "Employees, positions, pay setup, time and attendance, and workforce provisions.",
        to: "/hr",
        icon: Users,
        roles: HR_ROLES,
      },
      {
        title: "Scheduling",
        description: "Plan course sessions, venues and instructor allocation.",
        to: "/scheduling",
        icon: CalendarDays,
        roles: CENTRE_ROLES,
      },
      {
        title: "Enrolments",
        description: "Book learners, verify payments and allocate session seats.",
        to: "/enrolments",
        icon: ClipboardList,
        roles: CENTRE_ROLES,
      },
      {
        title: "Certificates",
        description: "Issue, approve, print and release certificates and ID cards.",
        to: "/certificates",
        icon: Award,
        roles: CERTIFICATE_READ,
      },
      {
        title: "Medicals",
        description: "Record and review medical fitness for training and certification.",
        to: "/medicals",
        icon: Stethoscope,
        roles: MEDICAL_ROLES,
      },
    ],
  },
  {
    label: "Finance",
    items: [
      {
        title: "Finance Workspace",
        description:
          "Chart of accounts, journals, pay runs, payslips, payment files and tax policy.",
        to: "/finance",
        icon: Landmark,
        roles: FINANCE_ROLES,
      },
      {
        title: "Billing",
        description: "Corporate accounts, invoices and outstanding balances.",
        to: "/billing",
        icon: ReceiptText,
        roles: BILLING_ROLES,
      },
    ],
  },
  {
    label: "Course Setup",
    items: [
      {
        title: "Courses",
        description: "Manage training courses.",
        to: "/courses",
        icon: BookOpen,
        roles: USER_ADMIN_ROLES,
      },
      {
        title: "Course Modules",
        description: "Manage course modules used to assign instructors.",
        to: "/modules",
        icon: ListChecks,
        roles: USER_ADMIN_ROLES,
      },
      {
        title: "Course Items",
        description: "Manage lines that are printed in some certificates.",
        to: "/items",
        icon: FileText,
        roles: USER_ADMIN_ROLES,
      },
    ],
  },
  {
    label: "Reference Data",
    items: [
      {
        title: "Companies",
        description: "Manage companies.",
        to: "/companies",
        icon: Building2,
        roles: USER_ADMIN_ROLES,
      },
      {
        title: "States",
        description: "Manage states master table.",
        to: "/states",
        icon: MapPin,
        roles: USER_ADMIN_ROLES,
      },
      {
        title: "Nationalities",
        description: "Manage nationalities.",
        to: "/nationalities",
        icon: Globe2,
        roles: USER_ADMIN_ROLES,
      },
    ],
  },
  {
    label: "Access",
    items: [
      {
        title: "Users",
        description: "Manage Axis users.",
        to: "/users",
        icon: ShieldCheck,
        roles: USER_ADMIN_ROLES,
      },
      {
        title: "User Roles",
        description: "Manage user roles.",
        to: "/roles",
        icon: UserCog,
        roles: USER_ADMIN_ROLES,
      },
    ],
  },
  {
    label: "Administration",
    items: [
      {
        title: "Notifications",
        description: "Review delivery history and maintain message templates.",
        to: "/notifications",
        icon: Bell,
        roles: ADMIN_TOOLS_ROLES,
      },
      {
        title: "Documents",
        description: "Search stored documents and upload supporting files.",
        to: "/documents",
        icon: Files,
        roles: ADMIN_TOOLS_ROLES,
      },
      {
        title: "Audit Trail",
        description: "Inspect the append-only record of system activity.",
        to: "/audit",
        icon: ScrollText,
        roles: ADMIN_TOOLS_ROLES,
      },
      {
        title: "Workflow Admin",
        description: "Maintain workflow statuses and inspect approval history.",
        to: "/workflow-admin",
        icon: GitBranch,
        roles: ADMIN_TOOLS_ROLES,
      },
      {
        title: "Integration",
        description: "Monitor outbox events, webhooks and external references.",
        to: "/integration",
        icon: PlugZap,
        roles: ADMIN_TOOLS_ROLES,
      },
      {
        title: "Report Access",
        description: "Control which roles may run each reporting dataset.",
        to: "/report-access",
        icon: LockKeyhole,
        roles: ADMIN_TOOLS_ROLES,
      },
      {
        title: "Reporting",
        description: "See training statistics",
        to: "/reports",
        icon: ChartNoAxesCombined,
        roles: REPORTING_ROLES,
      },
      {
        title: "Backup",
        description: "Run several backup processes",
        to: "/backup",
        icon: Database,
        roles: USER_ADMIN_ROLES,
      },
    ],
  },
];

export const HR_PAY_ROLES = HR_MANAGER_ROLES;
