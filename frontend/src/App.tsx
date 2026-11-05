import { lazy } from "react";
import type { ReactNode } from "react";
import { Link, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { ShieldAlert } from "lucide-react";
import { useAuth } from "./auth/context";
import type { RoleCode } from "./api/types";
import { AppShell } from "./components/AppShell";
import { LoginPage } from "./pages/LoginPage";

const DashboardPage = lazy(() =>
  import("./pages/DashboardPage").then((module) => ({ default: module.DashboardPage })),
);
const WorkflowPage = lazy(() =>
  import("./pages/WorkflowPage").then((module) => ({ default: module.WorkflowPage })),
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
const UsersPage = lazy(() =>
  import("./pages/UsersPage").then((module) => ({ default: module.UsersPage })),
);

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
      <Route element={<RequireAuth />}>
        <Route index element={<DashboardPage />} />
        <Route path="workflow" element={<WorkflowPage />} />
        <Route
          path="learners"
          element={
            <Guard roles={["admin", "front_desk", "training_coordinator", "accounts", "due_diligence", "printer"]}>
              <LearnersPage />
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
        <Route
          path="users"
          element={
            <Guard roles={[]}>
              <UsersPage />
            </Guard>
          }
        />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}
