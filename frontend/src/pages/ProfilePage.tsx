import { useState } from "react";
import type { FormEvent } from "react";
import { Link } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import {
  BookOpen,
  KeyRound,
  LogOut,
  Moon,
  ShieldCheck,
  Sun,
  UserRound,
} from "lucide-react";
import { request } from "../api/client";
import { useAuth } from "../auth/context";
import {
  ROLE_LABELS,
  displayName,
  initials,
  roleNames,
  USER_ADMIN_ROLES,
  can,
} from "../auth/roles";
import { Badge, Button, Card, Field, Input, PageHeader } from "../components/ui";
import { useToast } from "../components/toastContext";
import { detailFor, errorMessage } from "../lib/format";
import { manualForRole } from "../lib/manuals";
import { useTheme } from "../theme/context";

interface PasswordForm {
  current_password: string;
  new_password: string;
  confirm_password: string;
}

const EMPTY_PASSWORD_FORM: PasswordForm = {
  current_password: "",
  new_password: "",
  confirm_password: "",
};

export function ProfilePage() {
  const { user, signOut } = useAuth();
  const { theme, toggle } = useTheme();
  const toast = useToast();
  const [editingPassword, setEditingPassword] = useState(false);
  const [passwordForm, setPasswordForm] = useState<PasswordForm>(EMPTY_PASSWORD_FORM);

  const changePassword = useMutation({
    mutationFn: () =>
      request<void>("/auth/password", {
        method: "POST",
        body: JSON.stringify(passwordForm),
      }),
    onSuccess: () => {
      setPasswordForm(EMPTY_PASSWORD_FORM);
      setEditingPassword(false);
      toast.push("Password successfully changed.");
    },
    onError: (error) => {
      if (!detailFor(error, "current_password") && !detailFor(error, "new_password") && !detailFor(error, "confirm_password")) {
        toast.push(errorMessage(error), "error");
      }
    },
  });

  if (!user) return null;

  const manuals = user.role_codes.map(manualForRole);
  const hasFieldError =
    Boolean(detailFor(changePassword.error, "current_password")) ||
    Boolean(detailFor(changePassword.error, "new_password")) ||
    Boolean(detailFor(changePassword.error, "confirm_password"));

  function setPasswordField(field: keyof PasswordForm, value: string) {
    setPasswordForm((current) => ({ ...current, [field]: value }));
  }

  function closePasswordEditor() {
    if (changePassword.isPending) return;
    setPasswordForm(EMPTY_PASSWORD_FORM);
    changePassword.reset();
    setEditingPassword(false);
  }

  function submitPassword(event: FormEvent) {
    event.preventDefault();
    changePassword.mutate();
  }

  return (
    <>
      <PageHeader
        eyebrow="Account"
        title="Your profile"
        description="The identity carried into every workflow transition, audit event and approval in this console."
      />
      <div className="profile-grid">
        <Card>
          <div className="profile-identity">
            <span className="avatar avatar-lg">{initials(user)}</span>
            <div>
              <h2>{displayName(user)}</h2>
              <p className="mono">@{user.username}</p>
              <p>{user.email || "No email on file"}</p>
            </div>
          </div>
          <dl className="detail-grid">
            <div>
              <dt className="detail-label">Status</dt>
              <dd>
                <Badge tone={user.is_active ? "ok" : "danger"}>
                  {user.is_active ? "Active" : "Inactive"}
                </Badge>
              </dd>
            </div>
            <div>
              <dt className="detail-label">Staff access</dt>
              <dd>{user.is_staff ? "Staff" : "Restricted"}</dd>
            </div>
            <div>
              <dt className="detail-label">Roles</dt>
              <dd>{roleNames(user.role_codes)}</dd>
            </div>
            <div>
              <dt className="detail-label">Timezone</dt>
              <dd>Africa/Lagos</dd>
            </div>
          </dl>
          <div className="detail-section">
            <h3>Role assignments</h3>
            <div className="badge-row">
              {user.role_codes.map((role) => (
                <Badge key={role} tone="brand">
                  {ROLE_LABELS[role] ?? role}
                </Badge>
              ))}
            </div>
          </div>

          <div className="detail-section">
            <h3>Preferences</h3>
            <div className="preference-row">
              <span>
                <strong>Appearance</strong>
                <small>{theme === "dark" ? "Dark theme is on" : "Light theme is on"}</small>
              </span>
              <Button
                size="sm"
                aria-pressed={theme === "dark"}
                onClick={toggle}
              >
                {theme === "dark" ? (
                  <Sun size={14} aria-hidden="true" />
                ) : (
                  <Moon size={14} aria-hidden="true" />
                )}
                {theme === "dark" ? "Use light" : "Use dark"}
              </Button>
            </div>
          </div>

          <div className="detail-section">
            <h3>Password</h3>
            {!editingPassword ? (
              <Button size="sm" onClick={() => setEditingPassword(true)}>
                <KeyRound size={14} aria-hidden="true" /> Change password
              </Button>
            ) : (
              <form className="password-form" onSubmit={submitPassword}>
                <Field
                  label="Current password"
                  htmlFor="current-password"
                  error={detailFor(changePassword.error, "current_password")}
                >
                  <Input
                    id="current-password"
                    type="password"
                    autoComplete="current-password"
                    required
                    value={passwordForm.current_password}
                    onChange={(event) => setPasswordField("current_password", event.target.value)}
                  />
                </Field>
                <Field
                  label="New password"
                  htmlFor="new-password"
                  hint="Use at least eight characters and avoid your username or a common password."
                  error={detailFor(changePassword.error, "new_password")}
                >
                  <Input
                    id="new-password"
                    type="password"
                    autoComplete="new-password"
                    required
                    value={passwordForm.new_password}
                    onChange={(event) => setPasswordField("new_password", event.target.value)}
                  />
                </Field>
                <Field
                  label="Retype password"
                  htmlFor="confirm-password"
                  error={detailFor(changePassword.error, "confirm_password")}
                >
                  <Input
                    id="confirm-password"
                    type="password"
                    autoComplete="new-password"
                    required
                    value={passwordForm.confirm_password}
                    onChange={(event) => setPasswordField("confirm_password", event.target.value)}
                  />
                </Field>
                {changePassword.isError && !hasFieldError ? (
                  <div className="form-error" role="alert">
                    {errorMessage(changePassword.error)}
                  </div>
                ) : null}
                <div className="row-actions">
                  <Button
                    type="button"
                    size="sm"
                    disabled={changePassword.isPending}
                    onClick={closePasswordEditor}
                  >
                    Cancel
                  </Button>
                  <Button type="submit" size="sm" variant="primary" busy={changePassword.isPending}>
                    Change password
                  </Button>
                </div>
              </form>
            )}
          </div>

          <div className="detail-section profile-actions">
            {can(user, USER_ADMIN_ROLES) ? (
              <Link className="btn btn-secondary btn-md" to="/users">
                <ShieldCheck size={16} aria-hidden="true" /> Manage team access
              </Link>
            ) : null}
            <Button variant="danger" onClick={() => void signOut()}>
              <LogOut size={16} aria-hidden="true" /> Sign out
            </Button>
          </div>
        </Card>

        <div className="profile-side">
          <Card
            title="Role manuals"
            aside={<span className="card-note">Open in this console</span>}
          >
            {manuals.length ? (
              <ul className="role-manual-list">
                {manuals.map((manual) => (
                  <li key={manual.file}>
                    <span>
                      <strong>{manual.title}</strong>
                      <small>{ROLE_LABELS[manual.role]}</small>
                    </span>
                    <Link className="btn btn-secondary btn-sm" to={`/manuals/${manual.file}`}>
                      <BookOpen size={14} aria-hidden="true" /> View manual
                    </Link>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="hint">No role has been assigned to this account yet.</p>
            )}
          </Card>

          <Card title="Access notes">
            <ul className="plain-list">
              <li>
                <span>
                  <strong>Role-based access</strong>
                  <small>Navigation and actions are filtered by your assigned roles.</small>
                </span>
                <UserRound size={16} aria-hidden="true" />
              </li>
              <li>
                <span>
                  <strong>Attributed actions</strong>
                  <small>Every approval, rejection and data change is written to the audit trail.</small>
                </span>
                <ShieldCheck size={16} aria-hidden="true" />
              </li>
              <li>
                <span>
                  <strong>Credentials</strong>
                  <small>Change your own password here; ask a system administrator for role changes.</small>
                </span>
                <KeyRound size={16} aria-hidden="true" />
              </li>
            </ul>
            <p className="hint catalogue-note">
              This console uses token authentication. Changing your password revokes other active
              sessions.
            </p>
          </Card>
        </div>
      </div>
    </>
  );
}
