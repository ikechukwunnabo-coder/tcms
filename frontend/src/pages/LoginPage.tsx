import { useState } from "react";
import type { FormEvent } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import { ArrowRight, Eye, EyeOff, KeyRound, ShieldCheck } from "lucide-react";
import { useAuth } from "../auth/context";
import { Button, Field, Input } from "../components/ui";
import { errorMessage } from "../lib/format";

export function LoginPage() {
  const { session, signIn } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  if (session) return <Navigate to="/" replace />;

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    setBusy(true);
    try {
      await signIn(identifier, password);
      const from = (location.state as { from?: string } | null)?.from;
      navigate(from && from !== "/login" ? from : "/", { replace: true });
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="login-page">
      <section className="login-editorial">
        <div className="login-brand">
          <span className="brand-mark">TC</span>
          <span>TASL TRAINING CENTRE</span>
        </div>

        <div className="login-pitch">
          <p className="login-kicker">Staff operations · Lagos</p>
          <h1>The training centre, in one operating rhythm.</h1>
          <p>
            Bookings, medicals, approvals, certificates and collections. One console, with the
            next action always in view.
          </p>
          <div className="login-rules">
            <div>
              <span>01</span>
              <p>Bookings move only through verified payment and allocated seats.</p>
            </div>
            <div>
              <span>02</span>
              <p>Certificates are issued, signed and released as distinct gates.</p>
            </div>
            <div>
              <span>03</span>
              <p>Every action is attributed, timestamped and audit-ready.</p>
            </div>
          </div>
        </div>

        <div className="login-stamp">
          <ShieldCheck size={17} aria-hidden="true" />
          <span>Role-controlled access · Authorised staff only</span>
        </div>
      </section>

      <section className="login-panel">
        <form className="login-form" onSubmit={submit}>
          <div className="login-form-head">
            <span className="login-icon">
              <KeyRound size={20} aria-hidden="true" />
            </span>
            <p className="page-eyebrow">Sign in</p>
            <h2>Open the operations console</h2>
            <p className="hint">Use the staff username or email issued by your administrator.</p>
          </div>

          {error ? (
            <div className="form-error" role="alert">
              {error}
            </div>
          ) : null}

          <Field label="Username or email" htmlFor="identifier">
            <Input
              id="identifier"
              name="identifier"
              autoComplete="username"
              autoFocus
              required
              value={identifier}
              onChange={(event) => setIdentifier(event.target.value)}
              placeholder="e.g. frontdesk"
            />
          </Field>

          <Field label="Password" htmlFor="password">
            <div className="password-wrap">
              <Input
                id="password"
                name="password"
                type={showPassword ? "text" : "password"}
                autoComplete="current-password"
                required
                value={password}
                onChange={(event) => setPassword(event.target.value)}
              />
              <button
                type="button"
                className="password-toggle"
                onClick={() => setShowPassword((current) => !current)}
                aria-label={showPassword ? "Hide password" : "Show password"}
              >
                {showPassword ? (
                  <EyeOff size={17} aria-hidden="true" />
                ) : (
                  <Eye size={17} aria-hidden="true" />
                )}
              </button>
            </div>
          </Field>

          <Button type="submit" variant="primary" busy={busy} className="login-submit">
            Sign in <ArrowRight size={16} aria-hidden="true" />
          </Button>

          <p className="login-foot">
            Account access is role-based. If your permissions look wrong, contact the system
            administrator. <Link to="/verify">Verify a certificate</Link>
          </p>
        </form>
        <p className="login-version">TCMS · Operations console · v0.1</p>
      </section>
    </div>
  );
}
