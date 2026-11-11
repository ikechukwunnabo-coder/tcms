import {
  BookOpen,
  Building2,
  ChartNoAxesCombined,
  ClipboardCheck,
  Database,
  FileSpreadsheet,
  FileText,
  Globe2,
  History,
  ListChecks,
  MapPin,
  ShieldCheck,
  UserCog,
  Users,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import type { RoleCode } from "../api/types";
import { LEARNER_ROLES, REPORTING_ROLES, USER_ADMIN_ROLES } from "../auth/roles";

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

export const AXIS_GROUPS: AxisNavGroup[] = [
  {
    label: "Tasks",
    items: [
      {
        title: "My Pending Tasks",
        description:
          "Act on the pending tasks related to your Role by approving, rejecting or updating training data.",
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
    label: "Admin Tools",
    items: [
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
