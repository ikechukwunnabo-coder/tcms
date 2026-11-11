import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  KeyRound,
  Pencil,
  Plus,
  ShieldCheck,
  Trash2,
  UserRound,
} from "lucide-react";
import { request } from "../api/client";
import type { Role, StaffUser, UserRoleAssignment } from "../api/types";
import { useAuth } from "../auth/context";
import { ROLE_LABELS } from "../auth/roles";
import { UserEditor } from "../components/UserEditor";
import {
  Badge,
  Button,
  Card,
  ConfirmDialog,
  EmptyState,
  ErrorState,
  Loading,
  Modal,
  PageHeader,
  StatusBadge,
} from "../components/ui";
import { useToast } from "../components/toastContext";
import { errorMessage, titleCase } from "../lib/format";

function displayName(user: StaffUser) {
  if (user.full_name) return user.full_name;
  return `${user.first_name} ${user.last_name}`.trim() || user.username;
}

export function UserDetailPage() {
  const { id } = useParams();
  const userId = Number(id);
  const validId = Number.isInteger(userId) && userId > 0;
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const toast = useToast();
  const { user: currentUser } = useAuth();
  const [editing, setEditing] = useState(false);
  const [addingRoles, setAddingRoles] = useState(false);
  const [removeOpen, setRemoveOpen] = useState(false);
  const [resetOpen, setResetOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [selected, setSelected] = useState<number[]>([]);
  const [newRoles, setNewRoles] = useState<number[]>([]);

  const user = useQuery({
    queryKey: ["user", userId],
    queryFn: () => request<StaffUser>(`/users/${userId}/`),
    enabled: validId,
  });

  const assigned = useQuery({
    queryKey: ["user-roles", userId],
    queryFn: () => request<UserRoleAssignment[]>(`/user-role/${userId}`),
    enabled: validId && user.isSuccess,
  });

  const available = useQuery({
    queryKey: ["user-roles-available", userId],
    queryFn: () => request<Role[]>(`/user-role/${userId}/available`),
    enabled: validId && user.isSuccess,
  });

  function refreshRoles() {
    void queryClient.invalidateQueries({ queryKey: ["user-roles", userId] });
    void queryClient.invalidateQueries({ queryKey: ["user-roles-available", userId] });
    void queryClient.invalidateQueries({ queryKey: ["user", userId] });
    void queryClient.invalidateQueries({ queryKey: ["users"] });
  }

  const assignRoles = useMutation({
    mutationFn: (roleIds: number[]) =>
      request<UserRoleAssignment[]>("/user-role", {
        method: "POST",
        body: JSON.stringify({ user: userId, roles: roleIds }),
      }),
    onSuccess: () => {
      setAddingRoles(false);
      setNewRoles([]);
      refreshRoles();
      toast.push("Roles assigned.");
    },
    onError: (error) => toast.push(errorMessage(error), "error"),
  });

  const removeRoles = useMutation({
    mutationFn: (relationIds: number[]) =>
      Promise.all(
        relationIds.map((relationId) =>
          request<void>(`/user-role/${relationId}/delete`, { method: "DELETE" }),
        ),
      ),
    onSuccess: () => {
      setRemoveOpen(false);
      setSelected([]);
      refreshRoles();
      toast.push("Roles removed.");
    },
    onError: (error) => {
      setRemoveOpen(false);
      toast.push(errorMessage(error), "error");
    },
  });

  const resetPassword = useMutation({
    mutationFn: () =>
      request<{ message: string }>(`/users/${userId}/reset-password/`, { method: "POST" }),
    onSuccess: (data) => {
      setResetOpen(false);
      toast.push(data.message);
    },
    onError: (error) => {
      setResetOpen(false);
      toast.push(errorMessage(error), "error");
    },
  });

  const deleteUser = useMutation({
    mutationFn: () => request<void>(`/users/${userId}/`, { method: "DELETE" }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["users"] });
      toast.push("Team member removed.");
      navigate("/users", { replace: true });
    },
    onError: (error) => {
      setDeleteOpen(false);
      toast.push(errorMessage(error), "error");
    },
  });

  if (!validId) {
    return <ErrorState message="This team member could not be found." />;
  }
  if (user.isLoading) return <Loading rows={7} />;
  if (user.isError || !user.data) {
    return <ErrorState message={errorMessage(user.error)} retry={() => void user.refetch()} />;
  }

  const assignedRows = assigned.data ?? [];
  const availableRoles = available.data ?? [];
  const selectableRows = assignedRows.filter((row) => row.code !== "system_admin");
  const allSelected =
    selectableRows.length > 0 && selectableRows.every((row) => selected.includes(row.id));
  const isSelf = currentUser?.id === user.data.id;

  function toggleSelected(relationId: number) {
    setSelected((current) =>
      current.includes(relationId)
        ? current.filter((id) => id !== relationId)
        : [...current, relationId],
    );
  }

  function toggleAll() {
    setSelected(allSelected ? [] : selectableRows.map((row) => row.id));
  }

  function toggleNewRole(roleId: number) {
    setNewRoles((current) =>
      current.includes(roleId)
        ? current.filter((id) => id !== roleId)
        : [...current, roleId],
    );
  }

  return (
    <>
      <PageHeader
        eyebrow="Access control"
        title={displayName(user.data)}
        description={`@${user.data.username} · ${user.data.email || "No email address"}`}
        actions={
          <>
            <Link className="btn btn-secondary btn-md" to="/users">
              <ArrowLeft size={16} aria-hidden="true" /> Back to team
            </Link>
            <Button onClick={() => setEditing(true)}>
              <Pencil size={16} aria-hidden="true" /> Edit user
            </Button>
            <Button
              disabled={!user.data.email}
              title={!user.data.email ? "Add an email address before sending a reset link." : undefined}
              onClick={() => setResetOpen(true)}
            >
              <KeyRound size={16} aria-hidden="true" /> Send reset link
            </Button>
            <Button
              variant="danger"
              disabled={isSelf}
              title={isSelf ? "You cannot delete your own account." : undefined}
              onClick={() => setDeleteOpen(true)}
            >
              <Trash2 size={16} aria-hidden="true" /> Delete
            </Button>
          </>
        }
      />

      <Card
        title={
          <span className="card-title-with-icon">
            <UserRound size={15} aria-hidden="true" /> User data
          </span>
        }
        aside={
          <StatusBadge
            status={user.data.is_active ? "active" : "inactive"}
            label={user.data.is_active ? "Active" : "Inactive"}
          />
        }
      >
        <div className="detail-grid">
          <div>
            <p className="detail-label">Username</p>
            <p className="mono">{user.data.username}</p>
          </div>
          <div>
            <p className="detail-label">Full name</p>
            <p>{displayName(user.data)}</p>
          </div>
          <div>
            <p className="detail-label">Email</p>
            <p>{user.data.email || "—"}</p>
          </div>
          <div>
            <p className="detail-label">Django staff access</p>
            <p className="inline-value">
              <ShieldCheck
                size={15}
                className={user.data.is_staff ? "ok-text" : "muted"}
                aria-hidden="true"
              />
              {user.data.is_staff ? "Enabled" : "Not enabled"}
            </p>
          </div>
          <div>
            <p className="detail-label">Assigned roles</p>
            <p>{assignedRows.length}</p>
          </div>
          <div>
            <p className="detail-label">Account state</p>
            <p>{user.data.is_active ? "Active" : "Inactive"}</p>
          </div>
        </div>
      </Card>

      <Card
        title="User roles assigned"
        aside={
          <div className="card-actions">
            <Button
              size="sm"
              disabled={!availableRoles.length}
              onClick={() => {
                setNewRoles([]);
                setAddingRoles(true);
              }}
            >
              <Plus size={14} aria-hidden="true" /> Add role
            </Button>
            <Button
              size="sm"
              variant="danger"
              disabled={!selected.length}
              onClick={() => setRemoveOpen(true)}
            >
              <Trash2 size={14} aria-hidden="true" /> Remove
            </Button>
          </div>
        }
      >
        {assigned.isLoading ? (
          <Loading rows={3} />
        ) : assigned.isError ? (
          <div className="error-inline">
            <p className="field-error">{errorMessage(assigned.error)}</p>
            <Button size="sm" onClick={() => void assigned.refetch()}>
              Retry
            </Button>
          </div>
        ) : assignedRows.length ? (
          <div className="table-wrap">
            <table className="table role-table">
              <thead>
                <tr>
                  <th className="check-cell">
                    <input
                      type="checkbox"
                      checked={allSelected}
                      disabled={!selectableRows.length}
                      onChange={toggleAll}
                      aria-label="Select all removable roles"
                    />
                  </th>
                  <th>Role</th>
                  <th>Code</th>
                  <th>Assignment</th>
                </tr>
              </thead>
              <tbody>
                {assignedRows.map((row) => {
                  const protectedRole = row.code === "system_admin";
                  return (
                    <tr key={row.id}>
                      <td className="check-cell">
                        <input
                          type="checkbox"
                          checked={selected.includes(row.id)}
                          disabled={protectedRole}
                          onChange={() => toggleSelected(row.id)}
                          aria-label={`Select ${row.name}`}
                        />
                      </td>
                      <td>
                        <strong>{row.name}</strong>
                      </td>
                      <td className="mono">{row.code}</td>
                      <td>
                        {protectedRole ? (
                          <Badge tone="warn">Protected</Badge>
                        ) : (
                          <Badge tone="ok">Removable</Badge>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState
            title="No roles assigned"
            body="This account has no role yet, so it cannot access staff modules."
            action={
              availableRoles.length ? (
                <Button onClick={() => setAddingRoles(true)}>
                  <Plus size={14} aria-hidden="true" /> Add role
                </Button>
              ) : undefined
            }
          />
        )}
        {assignedRows.some((row) => row.code === "system_admin") ? (
          <p className="hint page-note">The System Admin role cannot be removed.</p>
        ) : null}
      </Card>

      <p className="hint page-note">
        Role changes take effect on the member’s next request. Password reset links are delivered
        by email and expire automatically.
      </p>

      {editing ? (
        <UserEditor user={user.data} showRoles={false} onClose={() => setEditing(false)} />
      ) : null}

      <Modal
        open={addingRoles}
        onClose={() => setAddingRoles(false)}
        title="Add roles"
        description="Select the roles to assign to this member."
        footer={
          <>
            <Button onClick={() => setAddingRoles(false)}>Cancel</Button>
            <Button
              variant="primary"
              busy={assignRoles.isPending}
              disabled={!newRoles.length}
              onClick={() => assignRoles.mutate(newRoles)}
            >
              Add selected
            </Button>
          </>
        }
      >
        {available.isLoading ? (
          <Loading rows={3} />
        ) : available.isError ? (
          <p className="field-error">Could not load available roles. {errorMessage(available.error)}</p>
        ) : availableRoles.length ? (
          <div className="role-grid">
            {availableRoles.map((role) => (
              <label className="role-check" key={role.id}>
                <input
                  type="checkbox"
                  checked={newRoles.includes(role.id)}
                  onChange={() => toggleNewRole(role.id)}
                />
                <span>
                  {ROLE_LABELS[role.code] ?? titleCase(role.code)}
                  <span className="role-code">{role.code}</span>
                </span>
              </label>
            ))}
          </div>
        ) : (
          <p className="muted body-copy">Every role is already assigned to this member.</p>
        )}
      </Modal>

      <ConfirmDialog
        open={removeOpen}
        title="Remove selected roles"
        message={`Remove ${selected.length} role${selected.length === 1 ? "" : "s"} from ${displayName(
          user.data,
        )}? They will immediately lose access to the related modules.`}
        confirmLabel="Remove roles"
        tone="danger"
        busy={removeRoles.isPending}
        onConfirm={() => removeRoles.mutate(selected)}
        onClose={() => setRemoveOpen(false)}
      />

      <ConfirmDialog
        open={resetOpen}
        title="Send password reset link"
        message={`Send a password reset link to ${
          user.data.email || "this account"
        }? The member will choose a new password from the emailed link.`}
        confirmLabel="Send link"
        busy={resetPassword.isPending}
        onConfirm={() => resetPassword.mutate()}
        onClose={() => setResetOpen(false)}
      />

      <ConfirmDialog
        open={deleteOpen}
        title="Delete team member"
        message={`Delete ${displayName(
          user.data,
        )}? This removes the staff account and cannot be undone.`}
        confirmLabel="Delete user"
        tone="danger"
        busy={deleteUser.isPending}
        onConfirm={() => deleteUser.mutate()}
        onClose={() => setDeleteOpen(false)}
      />
    </>
  );
}
