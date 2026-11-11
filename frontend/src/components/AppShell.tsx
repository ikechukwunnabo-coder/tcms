import { Suspense, useEffect, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import {
  Award,
  CalendarDays,
  ClipboardList,
  LayoutDashboard,
  LogOut,
  Menu,
  ReceiptText,
  Stethoscope,
  UserRound,
  X,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useAuth } from "../auth/context";
import {
  BILLING_ROLES,
  CERTIFICATE_READ,
  MEDICAL_ROLES,
  can,
  displayName,
  initials,
  roleNames,
} from "../auth/roles";
import type { RoleCode } from "../api/types";
import { AXIS_GROUPS } from "../navigation/axis";
import { todayLabel } from "../lib/format";
import { Loading } from "./ui";

interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
  roles?: RoleCode[];
  end?: boolean;
}

interface NavGroup {
  label: string;
  items: NavItem[];
}

const HOME_ITEM: NavItem = {
  to: "/",
  label: "Home",
  icon: LayoutDashboard,
  end: true,
};

const AXIS_NAV_GROUPS: NavGroup[] = AXIS_GROUPS.map((group) => ({
  label: group.label,
  items: group.items.map((item) => ({
    to: item.to,
    label: item.title,
    icon: item.icon,
    roles: item.roles,
  })),
}));

const CENTRE_TOOLS: NavGroup = {
  label: "Centre tools",
  items: [
    { to: "/scheduling", label: "Scheduling", icon: CalendarDays },
    { to: "/enrolments", label: "Enrolments", icon: ClipboardList },
    { to: "/certificates", label: "Certificates", icon: Award, roles: CERTIFICATE_READ },
    { to: "/medicals", label: "Medicals", icon: Stethoscope, roles: MEDICAL_ROLES },
    { to: "/billing", label: "Billing", icon: ReceiptText, roles: BILLING_ROLES },
  ],
};

const NAV_GROUPS: NavGroup[] = [...AXIS_NAV_GROUPS, CENTRE_TOOLS];

function currentLabel(pathname: string, visible: NavItem[]) {
  if (pathname === "/") return "Home";
  if (pathname === "/workflow") return "All Training Records";
  if (/^\/learners\/\d+/.test(pathname)) return "Learner workspace";
  if (/^\/training-records\/\d+/.test(pathname)) return "Training workspace";
  if (/^\/reports\//.test(pathname)) return "Reporting";
  const match = [...visible]
    .sort((a, b) => b.to.length - a.to.length)
    .find((item) => (item.to === "/" ? pathname === "/" : pathname.startsWith(item.to)));
  return match?.label ?? "Home";
}

export function AppShell() {
  const { user, signOut } = useAuth();
  const [open, setOpen] = useState(false);
  const location = useLocation();

  useEffect(() => {
    setOpen(false);
    window.scrollTo({ top: 0, behavior: "instant" });
  }, [location.pathname]);

  const groups = NAV_GROUPS.map((group) => ({
    ...group,
    items: group.items.filter((item) => !item.roles || can(user, item.roles)),
  })).filter((group) => group.items.length);
  const visible = groups.flatMap((group) => group.items);

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
          <NavLink
            to={HOME_ITEM.to}
            end={HOME_ITEM.end}
            className={({ isActive }) => (isActive ? "nav-item active" : "nav-item")}
          >
            <HOME_ITEM.icon size={18} aria-hidden="true" />
            <span>{HOME_ITEM.label}</span>
          </NavLink>
          {groups.map((group) => (
            <div className="nav-group" key={group.label}>
              <p className="nav-group-label">{group.label}</p>
              {group.items.map((item) => {
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
            </div>
          ))}
        </nav>

        <div className="sidebar-foot">
          <div className="identity">
            <span className="avatar">{initials(user)}</span>
            <div>
              <strong>{displayName(user)}</strong>
              <span>{roleNames(user?.role_codes)}</span>
            </div>
          </div>
          <NavLink
            to="/profile"
            className={({ isActive }) => (isActive ? "nav-item active" : "nav-item")}
          >
            <UserRound size={18} aria-hidden="true" />
            <span>My Profile</span>
          </NavLink>
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
              <strong>{currentLabel(location.pathname, visible)}</strong>
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
