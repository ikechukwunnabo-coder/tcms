import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, Search, ShieldCheck, ShieldX } from "lucide-react";
import { ApiError, requestPublic } from "../api/client";
import type { CertificateVerification } from "../api/types";
import { Button, Input } from "../components/ui";
import { errorMessage, formatDate, titleCase } from "../lib/format";

const STATUS_LABELS: Record<string, string> = {
  valid: "Valid",
  expiring_soon: "Valid - expiring soon",
  expired: "Expired",
  renewed: "Superseded by renewal",
  void: "Voided",
  not_issued: "Not issued",
};

export function VerifyCertificatePage() {
  const { identifier } = useParams();
  const navigate = useNavigate();
  const [value, setValue] = useState(identifier ?? "");

  useEffect(() => {
    setValue(identifier ?? "");
  }, [identifier]);

  const verification = useQuery({
    queryKey: ["certificate-verification", identifier],
    queryFn: () =>
      requestPublic<CertificateVerification>(
        `/verify/${encodeURIComponent(identifier ?? "")}/`,
      ),
    enabled: Boolean(identifier),
    retry: false,
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    const next = value.trim();
    if (next) navigate(`/verify/${encodeURIComponent(next)}`);
  }

  const notFound =
    verification.error instanceof ApiError && verification.error.status === 404;
  const data = verification.data;

  return (
    <div className="verify-page">
      <header className="verify-topbar">
        <Link className="verify-brand" to="/login">
          <span className="brand-mark">TC</span>
          <span>TASL Training Centre</span>
        </Link>
        <Link className="btn btn-secondary btn-sm" to="/login">
          <ArrowLeft size={14} aria-hidden="true" /> Staff console
        </Link>
      </header>

      <main className="verify-main">
        <section className="verify-intro">
          <p className="page-eyebrow">Certificate registry</p>
          <h1>Verify a training certificate</h1>
          <p className="verify-lede">
            Enter the certificate number, or the training record reference printed on
            the certificate, to confirm that it was issued by TASL Training Centre.
          </p>
          <form className="verify-form" onSubmit={submit}>
            <label className="visually-hidden" htmlFor="certificate-identifier">
              Certificate number or training record reference
            </label>
            <Input
              id="certificate-identifier"
              name="identifier"
              value={value}
              onChange={(event) => setValue(event.target.value)}
              placeholder="e.g. T26001190 or 1042"
              autoComplete="off"
              autoFocus
            />
            <Button type="submit" variant="primary">
              <Search size={16} aria-hidden="true" /> Verify
            </Button>
          </form>
        </section>

        {identifier ? (
          <section className="verify-result-wrap" aria-live="polite">
            {verification.isLoading ? (
              <div className="verify-result verify-result-neutral">
                <p className="verify-result-kicker">Checking registry</p>
                <h2>Looking up {identifier}...</h2>
              </div>
            ) : notFound ? (
              <div className="verify-result verify-result-invalid" role="alert">
                <span className="verify-emblem">
                  <ShieldX size={26} aria-hidden="true" />
                </span>
                <div>
                  <p className="verify-result-kicker">No matching record</p>
                  <h2>Certificate not found</h2>
                  <p>
                    We could not find a certificate for <strong>{identifier}</strong>.
                    Check the reference and try again.
                  </p>
                </div>
              </div>
            ) : verification.isError ? (
              <div className="verify-result verify-result-invalid" role="alert">
                <span className="verify-emblem">
                  <ShieldX size={26} aria-hidden="true" />
                </span>
                <div>
                  <p className="verify-result-kicker">Verification unavailable</p>
                  <h2>We could not complete this check</h2>
                  <p>{errorMessage(verification.error)}</p>
                </div>
              </div>
            ) : data ? (
              <div
                className={`verify-result ${
                  data.is_valid ? "verify-result-valid" : "verify-result-invalid"
                }`}
              >
                <span className="verify-emblem">
                  {data.is_valid ? (
                    <ShieldCheck size={26} aria-hidden="true" />
                  ) : (
                    <ShieldX size={26} aria-hidden="true" />
                  )}
                </span>
                <div>
                  <p className="verify-result-kicker">
                    {data.is_valid ? "Registry confirmation" : "Registry record"}
                  </p>
                  <h2>
                    {data.is_valid
                      ? "Certificate is valid"
                      : "Certificate is not valid"}
                  </h2>
                  <p className="verify-statement">
                    We can confirm that <strong>{data.full_name}</strong> received a
                    certificate for <strong>{data.course}</strong>
                    {data.issued ? <> on {formatDate(data.issued)}</> : null}.
                  </p>
                  <dl className="verify-details">
                    <div>
                      <dt>Certificate no.</dt>
                      <dd className="mono">{data.certificate_no}</dd>
                    </div>
                    <div>
                      <dt>Status</dt>
                      <dd>{STATUS_LABELS[data.status] ?? titleCase(data.status)}</dd>
                    </div>
                    <div>
                      <dt>Issued</dt>
                      <dd>{formatDate(data.issued)}</dd>
                    </div>
                    <div>
                      <dt>Expires</dt>
                      <dd>{data.expiry ? formatDate(data.expiry) : "No expiry"}</dd>
                    </div>
                  </dl>
                  {data.expiry && data.is_valid ? (
                    <p className="verify-expiry">
                      This certificate will expire on <strong>{formatDate(data.expiry)}</strong>.
                    </p>
                  ) : null}
                </div>
              </div>
            ) : null}
          </section>
        ) : (
          <section className="verify-result-wrap">
            <div className="verify-result verify-result-neutral">
              <span className="verify-emblem">
                <ShieldCheck size={26} aria-hidden="true" />
              </span>
              <div>
                <p className="verify-result-kicker">How this works</p>
                <h2>A public check without personal data exposure</h2>
                <p>
                  Verification confirms the learner name, course, issue date and
                  validity. Medical records, contact details and payment information are
                  never shown.
                </p>
              </div>
            </div>
          </section>
        )}
      </main>

      <footer className="verify-footer">
        <p>TASL Training Centre certificate verification service</p>
        <Link to="/login">Staff sign in</Link>
      </footer>
    </div>
  );
}
