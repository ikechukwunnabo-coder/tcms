import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, ShieldCheck, UserPlus } from "lucide-react";
import { getList } from "../api/client";
import type { StaffUser } from "../api/types";
import { useAuth } from "../auth/context";
import { ROLE_LABELS, USER_ADMIN_ROLES, can } from "../auth/roles";
import { UserEditor } from "../components/UserEditor";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorState,
  Loading,
  PageHeader,
  Pagination,
  SearchInput,
  StatusBadge,
  Toolbar,
} from "../components/ui";
import { errorMessage, titleCase } from "../lib/format";
import { useDebounced } from "../lib/hooks";

function displayName(user: StaffUser) {
  if (user.full_name) return user.full_name;
  return `${user.first_name} ${user.last_name}`.trim() || user.username;
}

function initials(user: StaffUser) {
  const parts = displayName(user).split(/\s+/).filter(Boolean);
  return parts
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join("");
}

export function UsersPage() {
  const { user } = useAuth();
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  const [editor, setEditor] = useState<{ user?: StaffUser } | null>(null);
  const search = useDebounced(query);

  const users = useQuery({
    queryKey: ["users", search, page],
    queryFn: () => getList<StaffUser>("/users/", { search, page, page_size: 24 }),
    enabled: can(user, USER_ADMIN_ROLES),
  });

  if (!can(user, USER_ADMIN_ROLES)) {
    return (
      <EmptyState
        title="Team access is restricted"
        body="Only the System Admin role can manage staff accounts and role assignments."
      />
    );
  }
  if (users.isLoading) return <Loading rows={7} />;
  if (users.isError || !users.data) {
    return <ErrorState message={errorMessage(users.error)} retry={() => void users.refetch()} />;
  }

  return (
    <>
      <PageHeader
        eyebrow="Access control"
        title="Team access"
        description="Staff identities, role assignments and account status."
        actions={
          <Button variant="primary" onClick={() => setEditor({})}>
            <UserPlus size={16} aria-hidden="true" /> Add member
          </Button>
        }
      />

      <Card>
        <Toolbar>
          <SearchInput
            value={query}
            onChange={(value) => {
              setQuery(value);
              setPage(1);
            }}
            placeholder="Search username, name or email"
          />
          <span className="toolbar-count">{users.data.total} accounts</span>
        </Toolbar>

        {users.data.data.length ? (
          <>
            <div className="user-grid">
              {users.data.data.map((row) => (
                <Link
                  className="user-card"
                  key={row.id}
                  to={`/users/${row.id}`}
                  aria-label={`Open ${displayName(row)}`}
                >
                  <div className="user-card-top">
                    <span className="user-card-avatar" aria-hidden="true">
                      {initials(row)}
                    </span>
                    <StatusBadge
                      status={row.is_active ? "active" : "inactive"}
                      label={row.is_active ? "Active" : "Inactive"}
                    />
                  </div>
                  <div>
                    <h3 className="user-card-name">{displayName(row)}</h3>
                    <p className="user-card-username">@{row.username}</p>
                  </div>
                  <p className="user-card-email">{row.email || "No email address"}</p>
                  <div className="user-card-roles">
                    {row.role_codes.length ? (
                      row.role_codes.map((code) => (
                        <Badge key={code} tone="brand">
                          {ROLE_LABELS[code] ?? titleCase(code)}
                        </Badge>
                      ))
                    ) : (
                      <span className="muted">No roles assigned</span>
                    )}
                  </div>
                  <div className="user-card-foot">
                    <span className={row.is_staff ? "user-card-staff" : "muted"}>
                      <ShieldCheck size={14} aria-hidden="true" />
                      {row.is_staff ? "Django staff access" : "Console access only"}
                    </span>
                    <span className="user-card-cta">
                      View <ArrowRight size={14} aria-hidden="true" />
                    </span>
                  </div>
                </Link>
              ))}
            </div>
            <Pagination
              page={users.data.page}
              pageSize={users.data.page_size}
              total={users.data.total}
              onPage={setPage}
            />
          </>
        ) : (
          <EmptyState
            title="No accounts found"
            body={query ? "No member matches this search." : "Add the first staff member."}
            action={
              !query ? (
                <Button variant="primary" onClick={() => setEditor({})}>
                  Add member
                </Button>
              ) : undefined
            }
          />
        )}
      </Card>

      {editor ? <UserEditor user={editor.user} onClose={() => setEditor(null)} /> : null}
      <p className="hint page-note">
        System Admin is the only role that can manage staff accounts. Open a member to review
        their account details and assigned roles.
      </p>
    </>
  );
}
