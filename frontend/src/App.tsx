import { lazy } from "react";
import type { ReactNode } from "react";
import { Link, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { ShieldAlert } from "lucide-react";
import { useAuth } from "./auth/context";
import {
  ADMIN_TOOLS_ROLES,
  FINANCE_ROLES,
  HR_ROLES,
  LEARNER_ROLES,
  USER_ADMIN_ROLES,
} from "./auth/roles";
import type { RoleCode } from "./api/types";
import { AppShell } from "./components/AppShell";
import { LoginPage } from "./pages/LoginPage";

const DashboardPage = lazy(() =>
  import("./pages/DashboardPage").then((module) => ({ default: module.DashboardPage })),
);
const WorkflowPage = lazy(() =>
  import("./pages/WorkflowPage").then((module) => ({ default: module.WorkflowPage })),
);
const HrPage = lazy(() =>
  import("./pages/HrPage").then((module) => ({ default: module.HrPage })),
);
const FinancePage = lazy(() =>
  import("./pages/FinancePage").then((module) => ({ default: module.FinancePage })),
);
const NotificationsPage = lazy(() =>
  import("./pages/AdminPages").then((module) => ({
    default: module.NotificationsPage,
  })),
);
const DocumentsPage = lazy(() =>
  import("./pages/AdminPages").then((module) => ({
    default: module.DocumentsPage,
  })),
);
const AuditPage = lazy(() =>
  import("./pages/AdminPages").then((module) => ({ default: module.AuditPage })),
);
const WorkflowAdminPage = lazy(() =>
  import("./pages/AdminPages").then((module) => ({
    default: module.WorkflowAdminPage,
  })),
);
const IntegrationPage = lazy(() =>
  import("./pages/AdminPages").then((module) => ({
    default: module.IntegrationPage,
  })),
);
const ReportAccessPage = lazy(() =>
  import("./pages/AdminPages").then((module) => ({
    default: module.ReportAccessPage,
  })),
);
const LearnersPage = lazy(() =>
  import("./pages/LearnersPage").then((module) => ({ default: module.LearnersPage })),
);
const SchedulingPage = lazy(() =>
  import("./pages/SchedulingPage").then((module) => ({ default: module.SchedulingPage })),
);
const EnrolmentsPage = lazy(() =>
  import("./pages/EnrolmentsPage").then((module) => ({ default: module.EnrolmentsPage })),
);
const CertificatesPage = lazy(() =>
  import("./pages/CertificatesPage").then((module) => ({ default: module.CertificatesPage })),
);
const OpitoFilesPage = lazy(() =>
  import("./pages/OpitoFilesPage").then((module) => ({ default: module.OpitoFilesPage })),
);
const CoursesPage = lazy(() =>
  import("./pages/CoursesPage").then((module) => ({ default: module.CoursesPage })),
);
const BillingPage = lazy(() =>
  import("./pages/BillingPage").then((module) => ({ default: module.BillingPage })),
);
const MedicalsPage = lazy(() =>
  import("./pages/MedicalsPage").then((module) => ({ default: module.MedicalsPage })),
);
const ReportsPage = lazy(() =>
  import("./pages/ReportsPage").then((module) => ({ default: module.ReportsPage })),
);
const ReportDetailPage = lazy(() =>
  import("./pages/ReportDetailPage").then((module) => ({
    default: module.ReportDetailPage,
  })),
);
const UsersPage = lazy(() =>
  import("./pages/UsersPage").then((module) => ({ default: module.UsersPage })),
);
const UserDetailPage = lazy(() =>
  import("./pages/UserDetailPage").then((module) => ({ default: module.UserDetailPage })),
);
const RolesPage = lazy(() =>
  import("./pages/RolesPage").then((module) => ({ default: module.RolesPage })),
);
const PendingTasksPage = lazy(() =>
  import("./pages/ActivityPages").then((module) => ({ default: module.PendingTasksPage })),
);
const MyActivityPage = lazy(() =>
  import("./pages/ActivityPages").then((module) => ({ default: module.MyActivityPage })),
);
const ModulesPage = lazy(() =>
  import("./pages/CatalogueAdminPages").then((module) => ({ default: module.ModulesPage })),
);
const ItemsPage = lazy(() =>
  import("./pages/CatalogueAdminPages").then((module) => ({ default: module.ItemsPage })),
);
const ReferenceDataPage = lazy(() =>
  import("./pages/ReferenceDataPage").then((module) => ({ default: module.ReferenceDataPage })),
);
const ProfilePage = lazy(() =>
  import("./pages/ProfilePage").then((module) => ({ default: module.ProfilePage })),
);
const ManualPage = lazy(() =>
  import("./pages/ManualPage").then((module) => ({ default: module.ManualPage })),
);
const BackupPage = lazy(() =>
  import("./pages/BackupPage").then((module) => ({ default: module.BackupPage })),
);
const LearnerWorkspacePage = lazy(() =>
  import("./pages/LearnerWorkspacePage").then((module) => ({ default: module.LearnerWorkspacePage })),
);
const TrainingWorkspacePage = lazy(() =>
  import("./pages/TrainingWorkspacePage").then((module) => ({ default: module.TrainingWorkspacePage })),
);
const VerifyCertificatePage = lazy(() =>
  import("./pages/VerifyCertificatePage").then((module) => ({
    default: module.VerifyCertificatePage,
  })),
);

const TRAINING_READ: RoleCode[] = [
  "system_admin",
  "admin",
  "front_desk",
  "medic",
  "training_coordinator",
  "accounts",
  "due_diligence",
  "md",
  "printer",
  "verification",
  "reports",
];

function RequireAuth() {
  const { session } = useAuth();
  const location = useLocation();
  if (!session) {
    return (
      <Navigate
        to="/login"
        replace
        state={{ from: `${location.pathname}${location.search}` }}
      />
    );
  }
  return <AppShell />;
}

function Denied() {
  return (
    <div className="standalone-state">
      <ShieldAlert size={26} aria-hidden="true" />
      <h1>Access not available</h1>
      <p>Your role cannot open this part of the console.</p>
      <Link className="btn btn-secondary btn-md" to="/">
        Return to the operations board
      </Link>
    </div>
  );
}

function Guard({ roles, children }: { roles: RoleCode[]; children: ReactNode }) {
  const { user } = useAuth();
  const allowed = Boolean(
    user &&
      (user.role_codes.includes("system_admin") ||
        user.role_codes.some((role) => roles.includes(role))),
  );
  return allowed ? children : <Denied />;
}

function NotFound() {
  return (
    <div className="standalone-state">
      <h1>Page not found</h1>
      <p>The page you asked for does not exist in the operations console.</p>
      <Link className="btn btn-secondary btn-md" to="/">
        Return to the operations board
      </Link>
    </div>
  );
}

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/verify" element={<VerifyCertificatePage />} />
      <Route path="/verify/:identifier" element={<VerifyCertificatePage />} />
      <Route element={<RequireAuth />}>
        <Route index element={<DashboardPage />} />
        <Route path="tasks" element={<PendingTasksPage />} />
        <Route path="pending-tasks" element={<Navigate to="/tasks" replace />} />
        <Route path="activity" element={<MyActivityPage />} />
        <Route path="my-activity" element={<Navigate to="/activity" replace />} />
        <Route path="workflow" element={<WorkflowPage />} />
        <Route
          path="training-records"
          element={
            <Guard roles={LEARNER_ROLES}>
              <WorkflowPage />
            </Guard>
          }
        />
        <Route path="trainings" element={<Navigate to="/training-records" replace />} />
        <Route
          path="learners"
          element={
            <Guard roles={["admin", "front_desk", "training_coordinator", "accounts", "due_diligence", "printer"]}>
              <LearnersPage />
            </Guard>
          }
        />
        <Route
          path="learners/:id"
          element={
            <Guard roles={["admin", "front_desk", "training_coordinator", "accounts", "due_diligence", "printer"]}>
              <LearnerWorkspacePage />
            </Guard>
          }
        />
        <Route
          path="training-records/:id"
          element={
            <Guard roles={TRAINING_READ}>
              <TrainingWorkspacePage />
            </Guard>
          }
        />
        <Route
          path="courses"
          element={
            <Guard roles={["system_admin"]}>
              <CoursesPage />
            </Guard>
          }
        />
        <Route path="modules" element={<ModulesPage />} />
        <Route path="course-modules" element={<Navigate to="/modules" replace />} />
        <Route path="items" element={<ItemsPage />} />
        <Route path="course-items" element={<Navigate to="/items" replace />} />
        <Route path="reference" element={<ReferenceDataPage />} />
        <Route
          path="companies"
          element={
            <Guard roles={USER_ADMIN_ROLES}>
              <ReferenceDataPage initialSet="companies" />
            </Guard>
          }
        />
        <Route
          path="states"
          element={
            <Guard roles={USER_ADMIN_ROLES}>
              <ReferenceDataPage initialSet="states" />
            </Guard>
          }
        />
        <Route
          path="nationalities"
          element={
            <Guard roles={USER_ADMIN_ROLES}>
              <ReferenceDataPage initialSet="nationalities" />
            </Guard>
          }
        />
        <Route path="profile" element={<ProfilePage />} />
        <Route path="manuals/:file" element={<ManualPage />} />
        <Route
          path="backup"
          element={
            <Guard roles={["system_admin"]}>
              <BackupPage />
            </Guard>
          }
        />
        <Route
          path="hr"
          element={
            <Guard roles={HR_ROLES}>
              <HrPage />
            </Guard>
          }
        />
        <Route
          path="finance"
          element={
            <Guard roles={FINANCE_ROLES}>
              <FinancePage />
            </Guard>
          }
        />
        <Route path="scheduling" element={<SchedulingPage />} />
        <Route path="enrolments" element={<EnrolmentsPage />} />
        <Route
          path="certificates"
          element={
            <Guard roles={["admin", "front_desk", "training_coordinator", "accounts", "due_diligence", "printer"]}>
              <CertificatesPage />
            </Guard>
          }
        />
        <Route
          path="opito-files"
          element={
            <Guard roles={["admin", "front_desk", "training_coordinator", "accounts", "due_diligence", "printer"]}>
              <OpitoFilesPage />
            </Guard>
          }
        />
        <Route
          path="billing"
          element={
            <Guard roles={["admin", "accounts"]}>
              <BillingPage />
            </Guard>
          }
        />
        <Route
          path="medicals"
          element={
            <Guard roles={["admin", "front_desk", "medic"]}>
              <MedicalsPage />
            </Guard>
          }
        />
        <Route
          path="reports"
          element={
            <Guard roles={["md", "reports"]}>
              <ReportsPage />
            </Guard>
          }
        />
        <Route path="reporting" element={<Navigate to="/reports" replace />} />
        <Route
          path="reports/:dataset"
          element={
            <Guard roles={["md", "reports"]}>
              <ReportDetailPage />
            </Guard>
          }
        />
        <Route
          path="users"
          element={
            <Guard roles={[]}>
              <UsersPage />
            </Guard>
          }
        />
        <Route
          path="users/:id"
          element={
            <Guard roles={[]}>
              <UserDetailPage />
            </Guard>
          }
        />
        <Route
          path="roles"
          element={
            <Guard roles={USER_ADMIN_ROLES}>
              <RolesPage />
            </Guard>
          }
        />
        <Route path="user-roles" element={<Navigate to="/roles" replace />} />
        <Route
          path="notifications"
          element={
            <Guard roles={ADMIN_TOOLS_ROLES}>
              <NotificationsPage />
            </Guard>
          }
        />
        <Route
          path="documents"
          element={
            <Guard roles={ADMIN_TOOLS_ROLES}>
              <DocumentsPage />
            </Guard>
          }
        />
        <Route
          path="audit"
          element={
            <Guard roles={ADMIN_TOOLS_ROLES}>
              <AuditPage />
            </Guard>
          }
        />
        <Route
          path="workflow-admin"
          element={
            <Guard roles={ADMIN_TOOLS_ROLES}>
              <WorkflowAdminPage />
            </Guard>
          }
        />
        <Route
          path="integration"
          element={
            <Guard roles={ADMIN_TOOLS_ROLES}>
              <IntegrationPage />
            </Guard>
          }
        />
        <Route
          path="report-access"
          element={
            <Guard roles={ADMIN_TOOLS_ROLES}>
              <ReportAccessPage />
            </Guard>
          }
        />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}
