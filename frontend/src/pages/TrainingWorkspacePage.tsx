import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowRight,
  CalendarDays,
  Check,
  Download,
  FileUp,
  HeartPulse,
  Mail,
  Plus,
  Trash2,
  UserRound,
  XCircle,
} from "lucide-react";
import { downloadFile, request } from "../api/client";
import type {
  DailyMedicalCheck,
  DocumentRecord,
  TrainingInstructor,
  TrainingWorkspace,
} from "../api/types";
import { useAuth } from "../auth/context";
import {
  CERTIFICATE_READ,
  LEARNER_ROLES,
  can,
  roleLabelById,
} from "../auth/roles";
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
  Select,
  StatusBadge,
  Textarea,
} from "../components/ui";
import { useToast } from "../components/toastContext";
import { errorMessage, formatDate, formatDateTime, titleCase } from "../lib/format";
import { useReference } from "../lib/useReference";

const DOCUMENT_FIELDS = [
  { key: "foet_scan", kind: "foet_scan", label: "FOET scan" },
  { key: "payment_proof", kind: "payment_proof", label: "Payment proof" },
  { key: "welcome_letter", kind: "welcome_letter", label: "Welcome letter" },
] as const;

type DocumentField = (typeof DOCUMENT_FIELDS)[number]["key"];
const RECORD_WRITE_ROLES = [
  "system_admin",
  "admin",
  "front_desk",
  "medic",
  "training_coordinator",
  "accounts",
  "due_diligence",
  "md",
  "printer",
  "verification",
  "reports",
] as const;
const DOCUMENT_WRITE_ROLES = [
  "system_admin",
  "admin",
  "front_desk",
  "training_coordinator",
  "accounts",
  "due_diligence",
  "printer",
] as const;

function WorkflowActionModal({
  workspace,
  action,
  onClose,
}: {
  workspace: TrainingWorkspace;
  action: "approve" | "reject" | "cancel";
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [reason, setReason] = useState("");
  const mutation = useMutation({
    mutationFn: () =>
      request<{ status: number; code: string }>(`/approvals/${workspace.id}/advance/`, {
        method: "POST",
        body: JSON.stringify({ action, reason }),
      }),
    onSuccess: (result) => {
      void queryClient.invalidateQueries({ queryKey: ["training-workspace", workspace.id] });
      void queryClient.invalidateQueries({ queryKey: ["training-records"] });
      void queryClient.invalidateQueries({ queryKey: ["my-activity"] });
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      toast.push(`TR-${workspace.id} moved to ${result.code.replace(/_/g, " ")}.`);
      onClose();
    },
  });

  return (
    <Modal
      open
      onClose={onClose}
      title={action === "approve" ? "Advance record" : action === "reject" ? "Reject record" : "Cancel record"}
      description={`${workspace.learner_name} · ${workspace.course_code} · ${titleCase(workspace.status_code)}`}
      footer={
        <>
          <Button onClick={onClose}>Back</Button>
          <Button
            type="submit"
            form="workspace-action-form"
            variant={action === "approve" ? "primary" : "danger"}
            busy={mutation.isPending}
            disabled={action === "reject" && !reason.trim()}
          >
            {action === "approve" ? "Advance" : action === "reject" ? "Reject" : "Cancel record"}
          </Button>
        </>
      }
    >
      <form
        id="workspace-action-form"
        className="form-stack"
        onSubmit={(event) => {
          event.preventDefault();
          mutation.mutate();
        }}
      >
        {mutation.isError ? <div className="form-error">{errorMessage(mutation.error)}</div> : null}
        <Field
          label={action === "reject" ? "Rejection reason" : "Note (optional)"}
          htmlFor="workspace-reason"
        >
          <Textarea
            id="workspace-reason"
            rows={3}
            required={action === "reject"}
            value={reason}
            onChange={(event) => setReason(event.target.value)}
          />
        </Field>
      </form>
    </Modal>
  );
}

function DocumentSlot({
  workspace,
  field,
  label,
  kind,
  readOnly,
}: {
  workspace: TrainingWorkspace;
  field: DocumentField;
  label: string;
  kind: string;
  readOnly: boolean;
}) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const document =
    field === "foet_scan"
      ? workspace.foet_scan_document
      : field === "payment_proof"
        ? workspace.payment_proof_document
        : workspace.welcome_letter_document;
  const upload = useMutation({
    mutationFn: async (file: File) => {
      const body = new FormData();
      body.append("file", file);
      body.append("kind", kind);
      body.append("owner_type", "training_record");
      body.append("owner_id", String(workspace.id));
      const created = await request<DocumentRecord>("/documents/upload/", {
        method: "POST",
        body,
      });
      await request<TrainingWorkspace>(`/training-records/${workspace.id}/`, {
        method: "PATCH",
        body: JSON.stringify({ [field]: created.id }),
      });
      return created;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["training-workspace", workspace.id] });
      toast.push(`${label} uploaded.`);
    },
  });

  return (
    <div className="document-slot">
      <div>
        <strong>{label}</strong>
        {document ? (
          <small className="mono">{document.object_key.split("/").pop()}</small>
        ) : (
          <small>Not uploaded</small>
        )}
      </div>
      <div className="row-actions">
        {document ? (
          <Button
            size="sm"
            onClick={() =>
              void downloadFile(
                `/documents/${document.id}/download/`,
                document.object_key.split("/").pop() ?? "document",
              )
            }
          >
            <Download size={14} aria-hidden="true" /> Open
          </Button>
        ) : null}
        {!readOnly ? (
          <label className="btn btn-secondary btn-sm file-button">
            <FileUp size={14} aria-hidden="true" /> {document ? "Replace" : "Upload"}
            <input
              type="file"
              hidden
              onChange={(event) => {
                const file = event.target.files?.[0];
                if (file) upload.mutate(file);
                event.target.value = "";
              }}
            />
          </label>
        ) : null}
      </div>
    </div>
  );
}

export function TrainingWorkspacePage() {
  const { id } = useParams();
  const recordId = Number(id);
  const { user } = useAuth();
  const toast = useToast();
  const queryClient = useQueryClient();
  const references = useReference();
  const [action, setAction] = useState<"approve" | "reject" | "cancel" | null>(null);
  const [dateForm, setDateForm] = useState<{ start_date: string; end_date: string } | null>(null);
  const [instructorForm, setInstructorForm] = useState({
    instructor: "",
    module: "",
    training_date: "",
  });
  const [checkForm, setCheckForm] = useState({
    check_date: new Date().toISOString().slice(0, 10),
    systolic: "",
    diastolic: "",
    notes: "",
  });

  const workspace = useQuery({
    queryKey: ["training-workspace", recordId],
    queryFn: () => request<TrainingWorkspace>(`/training-records/${recordId}/workspace/`),
    enabled: Number.isFinite(recordId),
  });

  const writeAllowed = can(user, [...RECORD_WRITE_ROLES]);
  const documentsAllowed = can(user, [...DOCUMENT_WRITE_ROLES]);
  const learnerAccess = can(user, LEARNER_ROLES);
  const certificateAccess = can(user, CERTIFICATE_READ);
  const clinician = can(user, ["system_admin", "admin", "medic"]);

  const saveDates = useMutation({
    mutationFn: () =>
      request<TrainingWorkspace>(`/training-records/${recordId}/`, {
        method: "PATCH",
        body: JSON.stringify({
          start_date: dateForm?.start_date || null,
          end_date: dateForm?.end_date || null,
        }),
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["training-workspace", recordId] });
      toast.push("Training dates updated.");
      setDateForm(null);
    },
  });

  const resend = useMutation({
    mutationFn: () => request<unknown>(`/training-records/${recordId}/resend-cji/`, { method: "POST" }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["training-workspace", recordId] });
      toast.push("Current joining instruction re-sent.");
    },
    onError: (error) => toast.push(errorMessage(error), "error"),
  });

  const addInstructor = useMutation({
    mutationFn: () =>
      request<TrainingInstructor>("/training-instructors/", {
        method: "POST",
        body: JSON.stringify({
          training_record: recordId,
          instructor: Number(instructorForm.instructor),
          module: instructorForm.module ? Number(instructorForm.module) : null,
          training_date: instructorForm.training_date || null,
        }),
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["training-workspace", recordId] });
      setInstructorForm({ instructor: "", module: "", training_date: "" });
      toast.push("Instructor assigned.");
    },
  });

  const removeInstructor = useMutation({
    mutationFn: (assignmentId: number) =>
      request<void>(`/training-instructors/${assignmentId}/`, { method: "DELETE" }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["training-workspace", recordId] });
      toast.push("Instructor assignment removed.");
    },
  });

  const addCheck = useMutation({
    mutationFn: () =>
      request<DailyMedicalCheck>("/medical-checks/", {
        method: "POST",
        body: JSON.stringify({
          training_record: recordId,
          check_date: checkForm.check_date,
          systolic: checkForm.systolic ? Number(checkForm.systolic) : null,
          diastolic: checkForm.diastolic ? Number(checkForm.diastolic) : null,
          notes: checkForm.notes,
        }),
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["training-workspace", recordId] });
      setCheckForm({
        check_date: new Date().toISOString().slice(0, 10),
        systolic: "",
        diastolic: "",
        notes: "",
      });
      toast.push("Daily observation recorded.");
    },
  });

  if (workspace.isLoading) return <Loading rows={9} />;
  if (workspace.isError || !workspace.data) {
    return <ErrorState message={errorMessage(workspace.error)} retry={() => void workspace.refetch()} />;
  }

  const record = workspace.data;
  const status = record.status_detail;
  const nextRole = status.next_role;
  const canAct =
    Boolean(user?.is_staff && user.role_codes.includes("system_admin")) ||
    (nextRole !== null && Boolean(user?.roles.includes(nextRole)));
  const canCancel = canAct || can(user, ["system_admin", "admin"]);
  const editableDates = dateForm ?? {
    start_date: record.start_date ?? "",
    end_date: record.end_date ?? "",
  };

  return (
    <>
      <PageHeader
        eyebrow={`Training record TR-${record.id}`}
        title={`${record.learner_name} · ${record.course_code}`}
        description={`${record.course_detail.name} · ${formatDate(record.start_date)} to ${formatDate(record.end_date)}`}
        actions={
          <>
            {learnerAccess ? (
              <Link className="btn btn-secondary btn-md" to={`/learners/${record.learner}`}>
                Learner profile
              </Link>
            ) : null}
            {canAct ? (
              <>
                <Button variant="primary" onClick={() => setAction("approve")}>
                  <Check size={16} aria-hidden="true" /> Advance
                </Button>
                <Button variant="danger" onClick={() => setAction("reject")}>
                  <XCircle size={16} aria-hidden="true" /> Reject
                </Button>
              </>
            ) : null}
            {canCancel ? (
              <Button variant="ghost" onClick={() => setAction("cancel")}>
                Cancel record
              </Button>
            ) : null}
          </>
        }
      />

      <div className="status-strip">
        <StatusBadge status={record.status_code} label={status.name} />
        <span className="muted">
          {status.terminal ? "Terminal stage" : nextRole ? `Awaiting ${roleLabelById(nextRole)}` : "No next role assigned"}
        </span>
        <span className="status-strip-spacer" />
        <Badge tone={record.reject_reason ? "danger" : "neutral"}>
          {record.reject_reason ? "Returned for correction" : "No open rejection"}
        </Badge>
        {record.enrolment ? <Badge tone="neutral">Enrolment #{record.enrolment}</Badge> : null}
      </div>

      <div className="workspace-grid">
        <Card title="Delivery details">
          <dl className="detail-grid">
            <div>
              <dt className="detail-label">Course</dt>
              <dd>{record.course_detail.name}</dd>
            </div>
            <div>
              <dt className="detail-label">Course code</dt>
              <dd className="mono">{record.course_code}</dd>
            </div>
            <div>
              <dt className="detail-label">Start date</dt>
              <dd>{formatDate(record.start_date)}</dd>
            </div>
            <div>
              <dt className="detail-label">End date</dt>
              <dd>{formatDate(record.end_date)}</dd>
            </div>
            <div>
              <dt className="detail-label">Session</dt>
              <dd>{record.session ? `#${record.session}` : "Not linked"}</dd>
            </div>
            <div>
              <dt className="detail-label">Lead instructor</dt>
              <dd>{record.instructor || "Not set"}</dd>
            </div>
          </dl>
          {record.reject_reason ? (
            <div className="notice notice-warn">{record.reject_reason}</div>
          ) : null}
          {writeAllowed ? (
            <div className="detail-section">
              <h3>Training window</h3>
              <form
                className="form-stack compact-form"
                onSubmit={(event) => {
                  event.preventDefault();
                  saveDates.mutate();
                }}
              >
                <div className="form-grid">
                  <Field label="Start date" htmlFor="record-start-date">
                    <Input
                      id="record-start-date"
                      type="date"
                      value={editableDates.start_date}
                      onChange={(event) =>
                        setDateForm({ ...editableDates, start_date: event.target.value })
                      }
                    />
                  </Field>
                  <Field label="End date" htmlFor="record-end-date">
                    <Input
                      id="record-end-date"
                      type="date"
                      value={editableDates.end_date}
                      onChange={(event) =>
                        setDateForm({ ...editableDates, end_date: event.target.value })
                      }
                    />
                  </Field>
                </div>
                <Button type="submit" size="sm" busy={saveDates.isPending}>
                  Save dates
                </Button>
              </form>
            </div>
          ) : null}
          {documentsAllowed ? (
            <div className="detail-section">
              <h3>Documents</h3>
              <div className="document-list">
                {DOCUMENT_FIELDS.map((slot) => (
                  <DocumentSlot
                    key={slot.key}
                    workspace={record}
                    field={slot.key}
                    label={slot.label}
                    kind={slot.kind}
                    readOnly={false}
                  />
                ))}
              </div>
            </div>
          ) : null}
        </Card>

        <div className="workspace-main">
          <div className="split-grid workspace-pair">
            <Card
              title="Joining instruction"
              aside={<Mail size={16} aria-hidden="true" />}
            >
              {record.joining_instruction ? (
                <>
                  <dl className="detail-grid">
                    <div>
                      <dt className="detail-label">Version</dt>
                      <dd>v{record.joining_instruction.version}</dd>
                    </div>
                    <div>
                      <dt className="detail-label">Delivery</dt>
                      <dd>{titleCase(record.joining_instruction.delivery_status)}</dd>
                    </div>
                    <div>
                      <dt className="detail-label">Sent to</dt>
                      <dd>{record.joining_instruction.sent_to || "Not sent"}</dd>
                    </div>
                    <div>
                      <dt className="detail-label">Issued</dt>
                      <dd>{formatDateTime(record.joining_instruction.issued_at)}</dd>
                    </div>
                  </dl>
                  <Button
                    size="sm"
                    busy={resend.isPending}
                    onClick={() => resend.mutate()}
                  >
                    <Mail size={14} aria-hidden="true" /> Re-send current CJI
                  </Button>
                </>
              ) : (
                <p className="muted body-copy">
                  No current joining instruction. A CJI is issued when an enrolment is confirmed.
                </p>
              )}
            </Card>

            <Card
              title="Medical checks"
              aside={<HeartPulse size={16} aria-hidden="true" />}
            >
              {record.medical_checks.length ? (
                <ul className="plain-list">
                  {record.medical_checks.map((check) => (
                    <li key={check.id}>
                      <span>
                        <strong>{formatDate(check.check_date)}</strong>
                        <small>{check.notes || "No notes"}</small>
                      </span>
                      <Badge tone="neutral">
                        {check.systolic ?? "—"}/{check.diastolic ?? "—"} mmHg
                      </Badge>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="muted body-copy">No daily observations recorded.</p>
              )}
              {clinician ? (
                <form
                  className="form-stack compact-form"
                  onSubmit={(event) => {
                    event.preventDefault();
                    addCheck.mutate();
                  }}
                >
                  <Field label="Check date" htmlFor="check-date">
                    <Input
                      id="check-date"
                      type="date"
                      required
                      value={checkForm.check_date}
                      onChange={(event) => setCheckForm({ ...checkForm, check_date: event.target.value })}
                    />
                  </Field>
                  <div className="form-grid">
                    <Field label="Systolic" htmlFor="systolic">
                      <Input
                        id="systolic"
                        type="number"
                        min={40}
                        max={260}
                        value={checkForm.systolic}
                        onChange={(event) => setCheckForm({ ...checkForm, systolic: event.target.value })}
                      />
                    </Field>
                    <Field label="Diastolic" htmlFor="diastolic">
                      <Input
                        id="diastolic"
                        type="number"
                        min={20}
                        max={180}
                        value={checkForm.diastolic}
                        onChange={(event) => setCheckForm({ ...checkForm, diastolic: event.target.value })}
                      />
                    </Field>
                  </div>
                  <Field label="Notes" htmlFor="check-notes">
                    <Input
                      id="check-notes"
                      value={checkForm.notes}
                      onChange={(event) => setCheckForm({ ...checkForm, notes: event.target.value })}
                    />
                  </Field>
                  <Button type="submit" size="sm" busy={addCheck.isPending}>
                    <Plus size={14} aria-hidden="true" /> Record observation
                  </Button>
                </form>
              ) : null}
            </Card>
          </div>

          <Card
            title="Instructors & modules"
            aside={<UserRound size={16} aria-hidden="true" />}
          >
            {record.training_instructors.length ? (
              <div className="table-wrap">
                <table className="table">
                  <thead>
                    <tr>
                      <th>Instructor</th>
                      <th>Module</th>
                      <th>Training date</th>
                      <th aria-label="Actions" />
                    </tr>
                  </thead>
                  <tbody>
                    {record.training_instructors.map((assignment) => {
                      const instructor = references.data?.instructors.find(
                        (row) => row.id === assignment.instructor,
                      );
                      return (
                        <tr key={assignment.id}>
                          <td><strong>{instructor?.full_name ?? `Instructor #${assignment.instructor}`}</strong></td>
                          <td>{assignment.module_name || "All modules"}</td>
                          <td>{formatDate(assignment.training_date)}</td>
                          <td>
                            {writeAllowed ? (
                              <Button
                                size="sm"
                                variant="danger"
                                busy={removeInstructor.isPending}
                                onClick={() => removeInstructor.mutate(assignment.id)}
                              >
                                <Trash2 size={14} aria-hidden="true" /> Remove
                              </Button>
                            ) : null}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="muted body-copy">No instructors assigned to this record.</p>
            )}
            {writeAllowed ? (
              <form
                className="inline-form"
                onSubmit={(event) => {
                  event.preventDefault();
                  addInstructor.mutate();
                }}
              >
                <Select
                  aria-label="Instructor"
                  required
                  value={instructorForm.instructor}
                  onChange={(event) =>
                    setInstructorForm({ ...instructorForm, instructor: event.target.value })
                  }
                >
                  <option value="">Choose instructor</option>
                  {references.data?.instructors.map((instructor) => (
                    <option key={instructor.id} value={instructor.id}>{instructor.full_name}</option>
                  ))}
                </Select>
                <Select
                  aria-label="Module"
                  value={instructorForm.module}
                  onChange={(event) =>
                    setInstructorForm({ ...instructorForm, module: event.target.value })
                  }
                >
                  <option value="">All modules</option>
                  {references.data?.modules.map((module) => (
                    <option key={module.id} value={module.id}>{module.name}</option>
                  ))}
                </Select>
                <Input
                  aria-label="Training date"
                  type="date"
                  value={instructorForm.training_date}
                  onChange={(event) =>
                    setInstructorForm({ ...instructorForm, training_date: event.target.value })
                  }
                />
                <Button type="submit" size="sm" busy={addInstructor.isPending}>
                  <Plus size={14} aria-hidden="true" /> Assign
                </Button>
              </form>
            ) : null}
          </Card>

          <div className="split-grid workspace-pair">
            <Card title="Training items">
              {record.items.length ? (
                <ul className="plain-list">
                  {record.items.map((item) => {
                    const catalogueItem = references.data?.items.find(
                      (row) => row.id === item.course_item,
                    );
                    return (
                      <li key={item.id}>
                        <span>
                          <strong>{catalogueItem?.name ?? `Item #${item.course_item}`}</strong>
                          <small>{item.score ? `Score ${item.score}` : "No score"}</small>
                        </span>
                        <Badge tone={item.passed === null ? "neutral" : item.passed ? "ok" : "danger"}>
                          {item.passed === null ? "Pending" : item.passed ? "Passed" : "Failed"}
                        </Badge>
                      </li>
                    );
                  })}
                </ul>
              ) : (
                <p className="muted body-copy">No training items recorded.</p>
              )}
            </Card>

            <Card title="Certification output">
              {record.certificates.length || record.id_cards.length ? (
                <ul className="plain-list">
                  {record.certificates.map((certificate) => (
                    <li key={`cert-${certificate.id}`}>
                      <span>
                        <strong className="mono">{certificate.certificate_no || "Pending number"}</strong>
                        <small>
                          Certificate · {formatDate(certificate.expiry_date)} ·{" "}
                          {certificate.voided_at ? "Void" : certificate.released_at ? "Released" : "Held"}
                        </small>
                      </span>
                      {certificateAccess ? (
                        <Button
                          size="sm"
                          onClick={() =>
                            void downloadFile(
                              `/certificates/${certificate.id}/document/`,
                              `${certificate.certificate_no || "certificate"}.pdf`,
                            )
                          }
                        >
                          <Download size={14} aria-hidden="true" /> PDF
                        </Button>
                      ) : null}
                    </li>
                  ))}
                  {record.id_cards.map((card) => (
                    <li key={`card-${card.id}`}>
                      <span>
                        <strong className="mono">{card.card_no}</strong>
                        <small>ID card · {formatDateTime(card.printed_at)}</small>
                      </span>
                      {certificateAccess ? (
                        <Button
                          size="sm"
                          onClick={() =>
                            void downloadFile(`/id-cards/${card.id}/document/`, `${card.card_no}.pdf`)
                          }
                        >
                          <Download size={14} aria-hidden="true" /> PDF
                        </Button>
                      ) : null}
                    </li>
                  ))}
                </ul>
              ) : (
                <EmptyState
                  title="No certification yet"
                  body="Certificates and ID cards issued against this record will appear here."
                />
              )}
              {certificateAccess ? (
                <Link className="text-link catalogue-note" to={`/certificates?learner=${record.learner}`}>
                  Open certificate desk <ArrowRight size={14} aria-hidden="true" />
                </Link>
              ) : null}
            </Card>
          </div>

          <Card title="Status history">
            {record.status_history.length ? (
              <ul className="timeline">
                {record.status_history.map((row) => (
                  <li key={row.id}>
                    <span className="timeline-mark ok">
                      <CalendarDays size={14} aria-hidden="true" />
                    </span>
                    <div>
                      <strong>{row.full_name}</strong>
                      <p>{formatDateTime(row.updated_at)}</p>
                    </div>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="muted body-copy">No status changes recorded.</p>
            )}
          </Card>
        </div>
      </div>

      {action ? (
        <WorkflowActionModal workspace={record} action={action} onClose={() => setAction(null)} />
      ) : null}
    </>
  );
}
