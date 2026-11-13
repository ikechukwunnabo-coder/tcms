import { Suspense, useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import {
  ChevronDown,
  ClipboardCheck,
  LayoutDashboard,
  LogOut,
  Menu,
  Moon,
  PanelLeftClose,
  PanelLeftOpen,
  Search,
  Sun,
  UserRound,
  X,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { request } from "../api/client";
import { useAuth } from "../auth/context";
import {
  can,
  displayName,
  initials,
  roleNames,
} from "../auth/roles";
import type { RoleCode } from "../api/types";
import { AXIS_GROUPS } from "../navigation/axis";
import { todayLabel } from "../lib/format";
import { useTheme } from "../theme/context";
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

const NAV_GROUPS: NavGroup[] = AXIS_NAV_GROUPS;
const SIDEBAR_STORAGE_KEY = "tcms.sidebar";

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

function initialCollapsed() {
  try {
    return localStorage.getItem(SIDEBAR_STORAGE_KEY) === "collapsed";
  } catch {
    return false;
  }
}

export function AppShell() {
  const { user, signOut } = useAuth();
  const { theme, toggle } = useTheme();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(initialCollapsed);
  const [searchOpen, setSearchOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [activeResult, setActiveResult] = useState(0);
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const searchInput = useRef<HTMLInputElement>(null);
  const userMenuRef = useRef<HTMLDivElement>(null);
  const location = useLocation();

  useEffect(() => {
    setOpen(false);
    setSearchOpen(false);
    setSearchQuery("");
    setUserMenuOpen(false);
    window.scrollTo({ top: 0, behavior: "instant" });
  }, [location.pathname]);

  useEffect(() => {
    try {
      localStorage.setItem(SIDEBAR_STORAGE_KEY, collapsed ? "collapsed" : "expanded");
    } catch {
      // Storage can be unavailable in private or restricted browser contexts.
    }
  }, [collapsed]);

  useEffect(() => {
    if (!searchOpen) return;
    const timer = window.setTimeout(() => searchInput.current?.focus(), 0);
    return () => window.clearTimeout(timer);
  }, [searchOpen]);

  useEffect(() => {
    setActiveResult(0);
  }, [searchQuery]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      const tag = target?.tagName;
      const typing =
        tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || target?.isContentEditable;
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setSearchOpen(true);
      } else if (event.key === "/" && !typing) {
        event.preventDefault();
        setSearchOpen(true);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    if (!userMenuOpen) return;
    const onPointerDown = (event: PointerEvent) => {
      if (!userMenuRef.current?.contains(event.target as Node)) setUserMenuOpen(false);
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setUserMenuOpen(false);
    };
    document.addEventListener("pointerdown", onPointerDown);
    window.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      window.removeEventListener("keydown", onKey);
    };
  }, [userMenuOpen]);

  const groups = NAV_GROUPS.map((group) => ({
    ...group,
    items: group.items.filter((item) => !item.roles || can(user, item.roles)),
  })).filter((group) => group.items.length);
  const visible = groups.flatMap((group) => group.items);
  const canManageTasks = visible.some((item) => item.to === "/tasks");
  const pendingTasks = useQuery({
    queryKey: ["pending-tasks", "topbar"],
    queryFn: () => request<{ total: number }>("/approvals/pending-tasks/?page=1&page_size=1"),
    enabled: canManageTasks,
    staleTime: 60_000,
    refetchInterval: 120_000,
  });
  const pendingTotal = pendingTasks.data?.total ?? 0;
  const searchable = [
    { ...HOME_ITEM, group: "Overview" },
    ...groups.flatMap((group) =>
      group.items.map((item) => ({ ...item, group: group.label })),
    ),
  ];
  const searchResults = searchable.filter((item) => {
    const haystack = `${item.label} ${item.group} ${item.to}`.toLowerCase();
    return haystack.includes(searchQuery.trim().toLowerCase());
  });

  function openWorkspace(to: string) {
    setSearchOpen(false);
    setSearchQuery("");
    navigate(to);
  }

  function onSearchKeyDown(event: React.KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Escape") {
      event.preventDefault();
      setSearchOpen(false);
    } else if (event.key === "ArrowDown") {
      event.preventDefault();
      setActiveResult((current) =>
        searchResults.length ? Math.min(current + 1, searchResults.length - 1) : 0,
      );
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActiveResult((current) => Math.max(current - 1, 0));
    } else if (event.key === "Enter" && searchResults[activeResult]) {
      event.preventDefault();
      openWorkspace(searchResults[activeResult].to);
    }
  }

  return (
    <div className={`app-shell ${collapsed ? "sidebar-collapsed" : ""}`}>
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
            aria-label={HOME_ITEM.label}
            title={HOME_ITEM.label}
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
                    aria-label={item.label}
                    title={item.label}
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
            aria-label="My Profile"
            title="My Profile"
            className={({ isActive }) => (isActive ? "nav-item active" : "nav-item")}
          >
            <UserRound size={18} aria-hidden="true" />
            <span>My Profile</span>
          </NavLink>
          <button
            type="button"
            className="nav-item nav-signout"
            onClick={() => void signOut()}
            aria-label="Sign out"
            title="Sign out"
          >
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
            <button
              type="button"
              className="icon-btn sidebar-toggle"
              onClick={() => setCollapsed((current) => !current)}
              aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
              aria-pressed={collapsed}
              title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            >
              {collapsed ? (
                <PanelLeftOpen size={18} aria-hidden="true" />
              ) : (
                <PanelLeftClose size={18} aria-hidden="true" />
              )}
            </button>
            <div>
              <p className="crumb">
                <span>TASL</span>
                <span aria-hidden="true">/</span>
                <span>Operations</span>
              </p>
              <strong>{currentLabel(location.pathname, visible)}</strong>
            </div>
          </div>
          <div className="topbar-right">
            <p className="today">{todayLabel()}</p>
            <button
              type="button"
              className="workspace-search-trigger"
              onClick={() => setSearchOpen(true)}
              aria-label="Search workspaces"
              aria-haspopup="dialog"
            >
              <Search size={15} aria-hidden="true" />
              <span>Search workspaces</span>
              <kbd>Ctrl K</kbd>
            </button>
            {canManageTasks ? (
              <Link
                className="topbar-task-link"
                to="/tasks"
                aria-label={
                  pendingTotal
                    ? `${pendingTotal} pending tasks`
                    : "Pending tasks"
                }
                title="Pending tasks"
              >
                <ClipboardCheck size={17} aria-hidden="true" />
                {pendingTotal ? <span>{pendingTotal > 99 ? "99+" : pendingTotal}</span> : null}
              </Link>
            ) : null}
            <div className="topbar-user" ref={userMenuRef}>
              <button
                type="button"
                className="user-menu-trigger"
                onClick={() => setUserMenuOpen((current) => !current)}
                aria-label="Open account menu"
                aria-haspopup="menu"
                aria-expanded={userMenuOpen}
              >
                <span className="avatar">{initials(user)}</span>
                <span className="user-menu-copy">
                  <strong>{displayName(user)}</strong>
                  <small>{roleNames(user?.role_codes)}</small>
                </span>
                <ChevronDown size={15} aria-hidden="true" />
              </button>
              {userMenuOpen ? (
                <div className="user-menu" role="menu">
                  <div className="user-menu-head">
                    <strong>{displayName(user)}</strong>
                    <span>{roleNames(user?.role_codes)}</span>
                  </div>
                  <Link
                    className="user-menu-item"
                    to="/profile"
                    role="menuitem"
                    onClick={() => setUserMenuOpen(false)}
                  >
                    <UserRound size={16} aria-hidden="true" />
                    My profile
                  </Link>
                  <button
                    type="button"
                    className="user-menu-item"
                    role="menuitem"
                    onClick={() => {
                      toggle();
                      setUserMenuOpen(false);
                    }}
                  >
                    {theme === "dark" ? (
                      <Sun size={16} aria-hidden="true" />
                    ) : (
                      <Moon size={16} aria-hidden="true" />
                    )}
                    {theme === "dark" ? "Use light theme" : "Use dark theme"}
                  </button>
                  <button
                    type="button"
                    className="user-menu-item user-menu-signout"
                    role="menuitem"
                    onClick={() => void signOut()}
                  >
                    <LogOut size={16} aria-hidden="true" />
                    Sign out
                  </button>
                </div>
              ) : null}
            </div>
          </div>
        </header>

        <main id="main" className="page">
          <Suspense fallback={<Loading rows={6} />}>
            <Outlet />
          </Suspense>
        </main>
      </div>

      {searchOpen ? (
        <div
          className="command-layer"
          role="presentation"
          onMouseDown={() => setSearchOpen(false)}
        >
          <div
            className="command-panel"
            role="dialog"
            aria-modal="true"
            aria-label="Search workspaces"
            onMouseDown={(event) => event.stopPropagation()}
          >
            <div className="command-input">
              <Search size={18} aria-hidden="true" />
              <input
                ref={searchInput}
                id="workspace-search"
                type="text"
                value={searchQuery}
                onChange={(event) => setSearchQuery(event.target.value)}
                onKeyDown={onSearchKeyDown}
                placeholder="Find a workspace, module or record type..."
                autoComplete="off"
                role="combobox"
                aria-expanded="true"
                aria-controls="workspace-results"
                aria-autocomplete="list"
                aria-activedescendant={
                  searchResults[activeResult] ? `workspace-result-${activeResult}` : undefined
                }
              />
              <kbd>Esc</kbd>
            </div>
            <div className="command-results" id="workspace-results" role="listbox">
              {searchResults.length ? (
                searchResults.map((item, index) => {
                  const Icon = item.icon;
                  return (
                    <button
                      type="button"
                      id={`workspace-result-${index}`}
                      key={`${item.group}-${item.to}`}
                      className={`command-result ${index === activeResult ? "active" : ""}`}
                      role="option"
                      aria-selected={index === activeResult}
                      onMouseEnter={() => setActiveResult(index)}
                      onClick={() => openWorkspace(item.to)}
                    >
                      <span className="command-result-icon">
                        <Icon size={17} aria-hidden="true" />
                      </span>
                      <span className="command-result-copy">
                        <strong>{item.label}</strong>
                        <small>{item.group}</small>
                      </span>
                      <span className="command-result-path mono">{item.to}</span>
                    </button>
                  );
                })
              ) : (
                <div className="command-empty">
                  <Search size={20} aria-hidden="true" />
                  <p>No workspace matches “{searchQuery}”.</p>
                </div>
              )}
            </div>
            <footer className="command-foot">
              <span>
                <kbd>↑</kbd>
                <kbd>↓</kbd> to navigate
              </span>
              <span>
                <kbd>Enter</kbd> to open
              </span>
            </footer>
          </div>
        </div>
      ) : null}
    </div>
  );
}
