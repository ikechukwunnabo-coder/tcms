import { useRef } from "react";
import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowRight,
  Award,
  CalendarDays,
  CreditCard,
  FileText,
  Stethoscope,
  Upload,
} from "lucide-react";
import { downloadFile, getList, request } from "../api/client";
import type {
  Certificate,
  IDCard,
  Learner,
  LearnerDocument,
  Medical,
  TrainingRecord,
} from "../api/types";
import { useAuth } from "../auth/context";
import { MEDICAL_ROLES, can } from "../auth/roles";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorState,
  Loading,
  PageHeader,
  StatusBadge,
} from "../components/ui";
import { useToast } from "../components/toastContext";
import { errorMessage, formatDate, formatDateTime, titleCase } from "../lib/format";
import { useReference } from "../lib/useReference";

function labelFor<T extends { id: number }>(
  rows: T[] | undefined,
  id: number | null,
  value: (row: T) => string,
) {
  if (id === null) return "Not set";
  const row = rows?.find((item) => item.id === id);
  return row ? value(row) : "Not set";
}

function DocumentUploadButton({
  learnerId,
  kind,
  label,
}: {
  learnerId: number;
  kind: "photo" | "id_scan";
  label: string;
}) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const input = useRef<HTMLInputElement>(null);
  const upload = useMutation({
    mutationFn: (file: File) => {
      const body = new FormData();
      body.append("learner", String(learnerId));
      body.append("kind", kind);
      body.append("file", file);
      return request<LearnerDocument>("/learner-documents/upload/", {
        method: "POST",
        body,
      });
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["learner", learnerId] });
      toast.push(`${label} uploaded.`);
    },
    onError: (error) => toast.push(errorMessage(error), "error"),
  });

  return (
    <>
      <input
        ref={input}
        className="visually-hidden"
        type="file"
        accept="image/*,.pdf"
        onChange={(event) => {
          const file = event.target.files?.[0];
          if (file) upload.mutate(file);
          event.target.value = "";
        }}
      />
      <Button size="sm" busy={upload.isPending} onClick={() => input.current?.click()}>
        <Upload size={14} aria-hidden="true" /> {label}
      </Button>
    </>
  );
}

export function LearnerWorkspacePage() {
  const { id } = useParams();
  const learnerId = Number(id);
  const { user } = useAuth();
  const toast = useToast();
  const references = useReference();
  const canSeeMedicals = can(user, MEDICAL_ROLES);

  const learner = useQuery({
    queryKey: ["learner", learnerId],
    queryFn: () => request<Learner>(`/learners/${learnerId}/`),
    enabled: Number.isFinite(learnerId),
  });
  const records = useQuery({
    queryKey: ["training-records", "learner", learnerId],
    queryFn: () => getList<TrainingRecord>("/training-records/", { learner: learnerId, page_size: 100 }),
    enabled: Number.isFinite(learnerId),
  });
  const certificates = useQuery({
    queryKey: ["certificates", "learner", learnerId],
    queryFn: () => getList<Certificate>("/certificates/", { learner: learnerId, page_size: 100 }),
    enabled: Number.isFinite(learnerId),
  });
  const idCards = useQuery({
    queryKey: ["id-cards", "learner", learnerId],
    queryFn: () => getList<IDCard>("/id-cards/", { learner: learnerId, page_size: 100 }),
    enabled: Number.isFinite(learnerId),
  });
  const medicals = useQuery({
    queryKey: ["medicals", "learner", learnerId],
    queryFn: () => getList<Medical>("/medicals/", { learner: learnerId, page_size: 100 }),
    enabled: Number.isFinite(learnerId) && canSeeMedicals,
  });

  if (learner.isLoading) return <Loading rows={8} />;
  if (learner.isError || !learner.data) {
    return <ErrorState message={errorMessage(learner.error)} retry={() => void learner.refetch()} />;
  }

  const profile = learner.data;
  const refs = references.data;
  const primaryContact =
    profile.contacts.find((contact) => contact.is_primary) ?? profile.contacts[0];

  return (
    <>
      <PageHeader
        eyebrow="Learner workspace"
        title={profile.full_name}
        description={`Badge ${profile.badge_no} · ${profile.vantage_id || "No Vantage ID"} · ${profile.active ? "Active learner" : "Inactive learner"}`}
        actions={
          <Link className="btn btn-secondary btn-md" to="/learners">
            Back to register
          </Link>
        }
      />
      <div className="workspace-grid">
        <Card title="Profile">
          <dl className="detail-grid">
            <div>
              <dt className="detail-label">Badge number</dt>
              <dd className="mono">{profile.badge_no}</dd>
            </div>
            <div>
              <dt className="detail-label">Vantage ID</dt>
              <dd className="mono">{profile.vantage_id || "—"}</dd>
            </div>
            <div>
              <dt className="detail-label">Company</dt>
              <dd>{labelFor(refs?.companies, profile.company, (row) => row.name)}</dd>
            </div>
            <div>
              <dt className="detail-label">Position</dt>
              <dd>{labelFor(refs?.positions, profile.position, (row) => row.name)}</dd>
            </div>
            <div>
              <dt className="detail-label">Nationality</dt>
              <dd>{labelFor(refs?.nationalities, profile.nationality, (row) => row.nationality)}</dd>
            </div>
            <div>
              <dt className="detail-label">State</dt>
              <dd>{labelFor(refs?.states, profile.state, (row) => row.name)}</dd>
            </div>
            <div>
              <dt className="detail-label">Sex</dt>
              <dd>{profile.sex === "M" ? "Male" : profile.sex === "F" ? "Female" : "Not set"}</dd>
            </div>
            <div>
              <dt className="detail-label">Date of birth</dt>
              <dd>{formatDate(profile.birth_date)}</dd>
            </div>
          </dl>
          <div className="detail-section">
            <h3>Contact</h3>
            {primaryContact ? (
              <p className="body-copy">
                <strong>{primaryContact.value}</strong>
                <span className="muted">
                  {" "}· {profile.contacts.length} contact{profile.contacts.length === 1 ? "" : "s"}
                </span>
              </p>
            ) : (
              <p className="muted body-copy">No contact details captured.</p>
            )}
          </div>
          <div className="detail-section">
            <div className="detail-heading">
              <h3>Documents</h3>
              <div className="row-actions">
                <DocumentUploadButton learnerId={profile.id} kind="photo" label="Photo" />
                <DocumentUploadButton learnerId={profile.id} kind="id_scan" label="ID scan" />
              </div>
            </div>
            {profile.documents.length ? (
              <ul className="plain-list">
                {profile.documents.map((document) => (
                  <li key={document.id}>
                    <span>
                      <strong>{titleCase(document.kind)}</strong>
                      <small>{document.object_key.split("/").pop()}</small>
                    </span>
                    <Button
                      size="sm"
                      onClick={async () => {
                        try {
                          await downloadFile(
                            `/learner-documents/${document.id}/download/`,
                            document.object_key.split("/").pop() ?? "document",
                          );
                        } catch (error) {
                          toast.push(errorMessage(error), "error");
                        }
                      }}
                    >
                      <FileText size={14} aria-hidden="true" /> Open
                    </Button>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="muted body-copy">No documents uploaded.</p>
            )}
          </div>
        </Card>

        <div className="workspace-main">
          <Card
            title="Training history"
            aside={<Badge tone="brand">{records.data?.total ?? 0} records</Badge>}
          >
            {records.isLoading ? (
              <Loading rows={3} />
            ) : records.isError ? (
              <ErrorState message={errorMessage(records.error)} retry={() => void records.refetch()} />
            ) : records.data?.data.length ? (
              <div className="table-wrap">
                <table className="table">
                  <thead>
                    <tr>
                      <th>Course</th>
                      <th>Dates</th>
                      <th>Stage</th>
                      <th aria-label="Actions" />
                    </tr>
                  </thead>
                  <tbody>
                    {records.data.data.map((record) => (
                      <tr key={record.id}>
                        <td>
                          <strong className="mono">{record.course_code}</strong>
                          <div className="cell-sub">TR-{record.id}</div>
                        </td>
                        <td>
                          {formatDate(record.start_date)}
                          <div className="cell-sub">to {formatDate(record.end_date)}</div>
                        </td>
                        <td><StatusBadge status={record.status_code} /></td>
                        <td>
                          <Link className="btn btn-ghost btn-sm" to={`/training-records/${record.id}`}>
                            Open <ArrowRight size={14} aria-hidden="true" />
                          </Link>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <EmptyState
                title="No training yet"
                body="Training records raised for this learner will appear here."
              />
            )}
          </Card>

          <div className="split-grid">
            <Card
              title="Certificates"
              aside={<Award size={16} aria-hidden="true" />}
            >
              {certificates.data?.data.length ? (
                <ul className="plain-list">
                  {certificates.data.data.map((certificate) => (
                    <li key={certificate.id}>
                      <span>
                        <strong className="mono">{certificate.certificate_no || "Pending number"}</strong>
                        <small>
                          {certificate.course_code} · {formatDate(certificate.expiry_date)}
                        </small>
                      </span>
                      <Badge tone={certificate.voided_at ? "danger" : certificate.released_at ? "ok" : "warn"}>
                        {certificate.voided_at ? "Void" : certificate.released_at ? "Released" : "Held"}
                      </Badge>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="muted body-copy">No certificates issued.</p>
              )}
            </Card>
            <Card
              title="ID cards"
              aside={<CreditCard size={16} aria-hidden="true" />}
            >
              {idCards.data?.data.length ? (
                <ul className="plain-list">
                  {idCards.data.data.map((card) => (
                    <li key={card.id}>
                      <span>
                        <strong className="mono">{card.card_no}</strong>
                        <small>{card.course_code}</small>
                      </span>
                      <small>{formatDateTime(card.printed_at)}</small>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="muted body-copy">No ID cards issued.</p>
              )}
            </Card>
          </div>

          {canSeeMedicals ? (
            <Card
              title="Medical records"
              aside={<Stethoscope size={16} aria-hidden="true" />}
            >
              {medicals.data?.data.length ? (
                <div className="table-wrap">
                  <table className="table">
                    <thead>
                      <tr>
                        <th>Record</th>
                        <th>Issued</th>
                        <th>Expires</th>
                        <th>Fitness</th>
                        <th>BP</th>
                      </tr>
                    </thead>
                    <tbody>
                      {medicals.data.data.map((medical) => (
                        <tr key={medical.id}>
                          <td className="mono">{medical.record_no}</td>
                          <td>{formatDate(medical.issued_date)}</td>
                          <td><span className="date-flag"><CalendarDays size={13} /> {formatDate(medical.expiry_date)}</span></td>
                          <td><Badge tone={medical.fitness === "unfit" ? "danger" : medical.fitness ? "ok" : "neutral"}>{titleCase(medical.fitness) || "Pending"}</Badge></td>
                          <td>{medical.systolic ?? "—"}/{medical.diastolic ?? "—"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="muted body-copy">No medical records captured.</p>
              )}
            </Card>
          ) : null}
        </div>
      </div>
    </>
  );
}
