import { Suspense, useEffect, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import {
  Award,
  CalendarDays,
  ChartNoAxesCombined,
  ClipboardList,
  GitPullRequest,
  LayoutDashboard,
  LogOut,
  Menu,
  ReceiptText,
  ShieldCheck,
  Stethoscope,
  Users,
  X,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useAuth } from "../auth/context";
import {
  BILLING_ROLES,
  CERTIFICATE_READ,
  LEARNER_ROLES,
  MEDICAL_ROLES,
  REPORTING_ROLES,
  USER_ADMIN_ROLES,
  can,
  displayName,
  initials,
  roleNames,
} from "../auth/roles";
import type { RoleCode } from "../api/types";
import { todayLabel } from "../lib/format";
import { Loading } from "./ui";

interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
  roles?: RoleCode[];
  end?: boolean;
}

const NAV: NavItem[] = [
  { to: "/", label: "Operations board", icon: LayoutDashboard, end: true },
  { to: "/workflow", label: "Workflow", icon: GitPullRequest },
  { to: "/learners", label: "Learners", icon: Users, roles: LEARNER_ROLES },
  { to: "/scheduling", label: "Scheduling", icon: CalendarDays },
  { to: "/enrolments", label: "Enrolments", icon: ClipboardList },
  { to: "/certificates", label: "Certificates", icon: Award, roles: CERTIFICATE_READ },
  { to: "/billing", label: "Billing", icon: ReceiptText, roles: BILLING_ROLES },
  { to: "/medicals", label: "Medicals", icon: Stethoscope, roles: MEDICAL_ROLES },
  { to: "/reports", label: "Reports", icon: ChartNoAxesCombined, roles: REPORTING_ROLES },
  { to: "/users", label: "Team access", icon: ShieldCheck, roles: USER_ADMIN_ROLES },
];

export function AppShell() {
  const { user, signOut } = useAuth();
  const [open, setOpen] = useState(false);
  const location = useLocation();

  useEffect(() => {
    setOpen(false);
    window.scrollTo({ top: 0, behavior: "instant" });
  }, [location.pathname]);

  const visible = NAV.filter((item) => !item.roles || can(user, item.roles));
  const current = visible.find((item) =>
    item.to === "/" ? location.pathname === "/" : location.pathname.startsWith(item.to),
  );

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <aside className={`sidebar ${open ? "sidebar-open" : ""}`} aria-label="Primary navigation">
        <div className="sidebar-brand">
          <div className="brand-mark" aria-hidden="true">
            TC
          </div>
          <div>
            <strong>TASL Training Centre</strong>
            <span>Operations console</span>
          </div>
          <button
            type="button"
            className="icon-btn sidebar-close"
            onClick={() => setOpen(false)}
            aria-label="Close navigation"
          >
            <X size={18} aria-hidden="true" />
          </button>
        </div>

        <nav className="sidebar-nav">
          {visible.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) => (isActive ? "nav-item active" : "nav-item")}
              >
                <Icon size={18} aria-hidden="true" />
                <span>{item.label}</span>
              </NavLink>
            );
          })}
        </nav>

        <div className="sidebar-foot">
          <div className="identity">
            <span className="avatar">{initials(user)}</span>
            <div>
              <strong>{displayName(user)}</strong>
              <span>{roleNames(user?.role_codes)}</span>
            </div>
          </div>
          <button type="button" className="nav-item nav-signout" onClick={() => void signOut()}>
            <LogOut size={18} aria-hidden="true" />
            <span>Sign out</span>
          </button>
          <p className="sidebar-note">Lagos · Africa/Lagos</p>
        </div>
      </aside>

      {open ? (
        <button
          type="button"
          className="sidebar-scrim"
          aria-label="Close navigation"
          onClick={() => setOpen(false)}
        />
      ) : null}

      <div className="app-main">
        <header className="topbar">
          <div className="topbar-left">
            <button
              type="button"
              className="icon-btn mobile-menu"
              onClick={() => setOpen(true)}
              aria-label="Open navigation"
            >
              <Menu size={20} aria-hidden="true" />
            </button>
            <div>
              <p className="crumb">TASL / Operations</p>
              <strong>{current?.label ?? "Operations"}</strong>
            </div>
          </div>
          <div className="topbar-right">
            <p className="today">{todayLabel()}</p>
            <span className="role-chip">{roleNames(user?.role_codes)}</span>
          </div>
        </header>

        <main id="main" className="page">
          <Suspense fallback={<Loading rows={6} />}>
            <Outlet />
          </Suspense>
        </main>
      </div>
    </div>
  );
}
