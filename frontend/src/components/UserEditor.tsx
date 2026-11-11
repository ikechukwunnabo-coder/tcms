import { useState } from "react";
import type { FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { request, getList } from "../api/client";
import type { Role, StaffUser } from "../api/types";
import { Button, Field, Input, Modal, Select } from "./ui";
import { useToast } from "./toastContext";
import { errorMessage } from "../lib/format";

export function UserEditor({
  user,
  onClose,
  showRoles = true,
}: {
  user?: StaffUser;
  onClose: () => void;
  showRoles?: boolean;
}) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const roles = useQuery({
    queryKey: ["roles"],
    queryFn: () => getList<Role>("/roles/", { page_size: 100 }),
    enabled: showRoles,
  });
  const [form, setForm] = useState({
    username: user?.username ?? "",
    first_name: user?.first_name ?? "",
    last_name: user?.last_name ?? "",
    email: user?.email ?? "",
    password: "",
    is_active: user?.is_active ?? true,
    is_staff: user?.is_staff ?? false,
    roles: (user?.roles ?? []) as number[],
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
      if (user) {
        void queryClient.invalidateQueries({ queryKey: ["user", user.id] });
      }
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
    };
    if (form.password) payload.password = form.password;
    if (showRoles) payload.roles = form.roles;
    save.mutate(payload);
  }

  return (
    <Modal
      open
      wide
      onClose={onClose}
      title={user ? `Edit ${user.username}` : "Add a team member"}
      description={
        showRoles
          ? "Roles determine which modules and workflow stages a staff member can act on."
          : "Account details can be updated here; roles are managed separately."
      }
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
        {showRoles ? (
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
        ) : null}
      </form>
    </Modal>
  );
}
