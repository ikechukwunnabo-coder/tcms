import { useState } from "react";
import type { FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Pencil, ShieldCheck, UserPlus } from "lucide-react";
import { getList, request } from "../api/client";
import type { Role, StaffUser } from "../api/types";
import { useAuth } from "../auth/context";
import { ROLE_LABELS, USER_ADMIN_ROLES, can } from "../auth/roles";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorState,
  Field,
  Input,
  Loading,
  Modal,
  PageHeader,
  Pagination,
  SearchInput,
  Select,
  StatusBadge,
  Toolbar,
} from "../components/ui";
import { useToast } from "../components/toastContext";
import { errorMessage, titleCase } from "../lib/format";
import { useDebounced } from "../lib/hooks";

function UserEditor({ user, onClose }: { user?: StaffUser; onClose: () => void }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const roles = useQuery({
    queryKey: ["roles"],
    queryFn: () => getList<Role>("/roles/", { page_size: 100 }),
  });
  const [form, setForm] = useState({
    username: user?.username ?? "",
    first_name: user?.first_name ?? "",
    last_name: user?.last_name ?? "",
    email: user?.email ?? "",
    password: "",
    is_active: user?.is_active ?? true,
    is_staff: user?.is_staff ?? false,
    roles: user?.roles ?? [] as number[],
  });

  const save = useMutation({
    mutationFn: (payload: Record<string, unknown>) =>
      user
        ? request<StaffUser>(`/users/${user.id}/`, {
            method: "PATCH",
            body: JSON.stringify(payload),
          })
        : request<StaffUser>("/users/", { method: "POST", body: JSON.stringify(payload) }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["users"] });
      toast.push(user ? "Team member updated." : "Team member added.");
      onClose();
    },
  });

  function set<K extends keyof typeof form>(key: K, value: (typeof form)[K]) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  function toggleRole(id: number) {
    setForm((current) => ({
      ...current,
      roles: current.roles.includes(id)
        ? current.roles.filter((role) => role !== id)
        : [...current.roles, id],
    }));
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    const payload: Record<string, unknown> = {
      username: form.username.trim(),
      first_name: form.first_name.trim(),
      last_name: form.last_name.trim(),
      email: form.email.trim(),
      is_active: form.is_active,
      is_staff: form.is_staff,
      roles: form.roles,
    };
    if (form.password) payload.password = form.password;
    save.mutate(payload);
  }

  return (
    <Modal
      open
      wide
      onClose={onClose}
      title={user ? `Edit ${user.username}` : "Add a team member"}
      description="Roles determine which modules and workflow stages a staff member can act on."
      footer={
        <>
          <Button onClick={onClose}>Cancel</Button>
          <Button type="submit" form="user-form" variant="primary" busy={save.isPending}>
            {user ? "Save member" : "Add member"}
          </Button>
        </>
      }
    >
      <form id="user-form" className="form-grid" onSubmit={submit}>
        {save.isError ? (
          <div className="form-error form-span" role="alert">
            {errorMessage(save.error)}
          </div>
        ) : null}
        <Field label="Username" htmlFor="user-username">
          <Input
            id="user-username"
            required
            autoComplete="off"
            value={form.username}
            onChange={(event) => set("username", event.target.value)}
          />
        </Field>
        <Field label="Email" htmlFor="user-email">
          <Input
            id="user-email"
            type="email"
            value={form.email}
            onChange={(event) => set("email", event.target.value)}
          />
        </Field>
        <Field label="First name" htmlFor="user-first">
          <Input
            id="user-first"
            value={form.first_name}
            onChange={(event) => set("first_name", event.target.value)}
          />
        </Field>
        <Field label="Last name" htmlFor="user-last">
          <Input
            id="user-last"
            value={form.last_name}
            onChange={(event) => set("last_name", event.target.value)}
          />
        </Field>
        <Field
          label={user ? "New password" : "Password"}
          htmlFor="user-password"
          hint={user ? "Leave blank to keep the current password." : undefined}
        >
          <Input
            id="user-password"
            type="password"
            autoComplete="new-password"
            required={!user}
            value={form.password}
            onChange={(event) => set("password", event.target.value)}
          />
        </Field>
        <Field label="Account status" htmlFor="user-active">
          <Select
            id="user-active"
            value={form.is_active ? "true" : "false"}
            onChange={(event) => set("is_active", event.target.value === "true")}
          >
            <option value="true">Active</option>
            <option value="false">Inactive</option>
          </Select>
        </Field>
        <Field
          label="Django staff access"
          htmlFor="user-staff"
          hint="Staff access is separate from TCMS roles."
        >
          <Select
            id="user-staff"
            value={form.is_staff ? "true" : "false"}
            onChange={(event) => set("is_staff", event.target.value === "true")}
          >
            <option value="false">No staff access</option>
            <option value="true">Staff access</option>
          </Select>
        </Field>
        <div className="form-span">
          <p className="field-label">Roles</p>
          <div className="role-grid">
            {(roles.data?.data ?? []).map((role) => (
              <label className="role-check" key={role.id}>
                <input
                  type="checkbox"
                  checked={form.roles.includes(role.id)}
                  onChange={() => toggleRole(role.id)}
                />
                <span>{role.name}</span>
              </label>
            ))}
          </div>
          {roles.isError ? (
            <p className="field-error">Could not load roles. {errorMessage(roles.error)}</p>
          ) : null}
        </div>
      </form>
    </Modal>
  );
}

export function UsersPage() {
  const { user } = useAuth();
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  const [editor, setEditor] = useState<{ user?: StaffUser } | null>(null);
  const search = useDebounced(query);

  const users = useQuery({
    queryKey: ["users", search, page],
    queryFn: () => getList<StaffUser>("/users/", { search, page, page_size: 25 }),
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
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Member</th>
                    <th>Email</th>
                    <th>Roles</th>
                    <th>Staff</th>
                    <th>Status</th>
                    <th aria-label="Actions" />
                  </tr>
                </thead>
                <tbody>
                  {users.data.data.map((row) => (
                    <tr key={row.id}>
                      <td>
                        <strong>
                          {row.first_name || row.last_name
                            ? `${row.first_name} ${row.last_name}`.trim()
                            : row.username}
                        </strong>
                        <div className="cell-sub mono">{row.username}</div>
                      </td>
                      <td>{row.email || "—"}</td>
                      <td>
                        <div className="badge-row">
                          {row.role_codes.length ? (
                            row.role_codes.map((code) => (
                              <Badge key={code} tone="brand">
                                {ROLE_LABELS[code] ?? titleCase(code)}
                              </Badge>
                            ))
                          ) : (
                            <span className="muted">No roles</span>
                          )}
                        </div>
                      </td>
                      <td>
                        <ShieldCheck
                          size={16}
                          className={row.is_staff ? "ok-text" : "muted"}
                          aria-label={row.is_staff ? "Staff access" : "No staff access"}
                        />
                      </td>
                      <td>
                        <StatusBadge
                          status={row.is_active ? "active" : "inactive"}
                          label={row.is_active ? "Active" : "Inactive"}
                        />
                      </td>
                      <td className="row-actions">
                        <Button size="sm" onClick={() => setEditor({ user: row })}>
                          <Pencil size={14} aria-hidden="true" /> Edit
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
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
        Role IDs are fixed by the TCMS role model. System Admin is the only role that can manage
        other accounts.
      </p>
    </>
  );
}
