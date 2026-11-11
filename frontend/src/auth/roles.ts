import type { RoleCode, StaffUser } from "../api/types";

export const ROLE_LABELS: Record<RoleCode, string> = {
  system_admin: "System admin",
  admin: "Admin",
  front_desk: "Front desk",
  medic: "Medic",
  training_coordinator: "Training coordinator",
  accounts: "Accounts",
  due_diligence: "Due diligence",
  md: "Managing director",
  printer: "Printer",
  instructor: "Instructor",
  reports: "Reports",
  verification: "Verification",
};

export const ROLE_IDS: Record<RoleCode, number> = {
  system_admin: 1,
  admin: 2,
  front_desk: 3,
  medic: 4,
  training_coordinator: 5,
  accounts: 6,
  due_diligence: 7,
  md: 8,
  printer: 9,
  instructor: 10,
  reports: 11,
  verification: 12,
};

export const ALL_ROLES = Object.keys(ROLE_LABELS) as RoleCode[];

export const LEARNER_ROLES: RoleCode[] = [
  "system_admin",
  "admin",
  "front_desk",
  "training_coordinator",
  "accounts",
  "due_diligence",
  "printer",
];
export const SCHEDULE_WRITE: RoleCode[] = ["system_admin", "admin", "training_coordinator"];
export const ENROLMENT_WRITE: RoleCode[] = [...SCHEDULE_WRITE, "accounts"];
export const CERTIFICATE_READ = LEARNER_ROLES;
export const CERTIFICATE_ISSUE: RoleCode[] = ["system_admin", "admin", "printer"];
export const CERTIFICATE_PRINT: RoleCode[] = ["system_admin", "printer"];
export const CERTIFICATE_MD: RoleCode[] = ["system_admin", "md"];
export const CERTIFICATE_RELEASE: RoleCode[] = ["system_admin", "admin"];
export const BILLING_ROLES: RoleCode[] = ["system_admin", "admin", "accounts"];
export const REPORTING_ROLES: RoleCode[] = ["system_admin", "md", "reports"];
export const MEDICAL_ROLES: RoleCode[] = ["system_admin", "admin", "front_desk", "medic"];
export const MEDICAL_WRITE: RoleCode[] = ["system_admin", "admin", "medic"];
export const USER_ADMIN_ROLES: RoleCode[] = ["system_admin"];

export function can(user: StaffUser | null | undefined, roles: RoleCode[]): boolean {
  if (!user) return false;
  if (user.is_staff && user.role_codes.includes("system_admin")) return true;
  return roles.some((role) => user.role_codes.includes(role));
}

export function roleLabelById(id: number | null | undefined): string {
  if (id === null || id === undefined) return "No next role";
  const found = (Object.keys(ROLE_IDS) as RoleCode[]).find((code) => ROLE_IDS[code] === id);
  return found ? ROLE_LABELS[found] : `Role ${id}`;
}

export function roleNames(codes: RoleCode[] | undefined): string {
  if (!codes?.length) return "No role";
  return codes.map((code) => ROLE_LABELS[code] ?? code).join(" · ");
}

export function initials(user: StaffUser | null | undefined): string {
  if (!user) return "?";
  const name = user.full_name || `${user.first_name} ${user.last_name}`.trim() || user.username;
  return name
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("");
}

export function displayName(user: StaffUser | null | undefined): string {
  if (!user) return "Signed out";
  return user.full_name || `${user.first_name} ${user.last_name}`.trim() || user.username;
}
