import { useState } from "react";
import type { FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Award, CreditCard, Download, PenLine, Printer, RotateCcw, Send, Upload } from "lucide-react";
import { downloadFile, getList, request } from "../api/client";
import type { Certificate, IDCard, TrainingRecord } from "../api/types";
import { useAuth } from "../auth/context";
import {
  CERTIFICATE_ISSUE,
  CERTIFICATE_MD,
  CERTIFICATE_PRINT,
  CERTIFICATE_RELEASE,
  can,
} from "../auth/roles";
import {
  Badge,
  Button,
  Card,
  ConfirmDialog,
  CsvButton,
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
  Toolbar,
} from "../components/ui";
import { useToast } from "../components/toastContext";
import { errorMessage, formatDate } from "../lib/format";
import { useDebounced } from "../lib/hooks";

function certificateState(certificate: Certificate) {
  if (certificate.voided_at) return { label: "Voided", tone: "danger" as const };
  if (certificate.released_at) return { label: "Released", tone: "ok" as const };
  if (certificate.md_approved_at) return { label: "Signed · awaiting release", tone: "warn" as const };
  return { label: "Issued", tone: "neutral" as const };
}

function IssueEditor({ onClose }: { onClose: () => void }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [record, setRecord] = useState("");
  const records = useQuery({
    queryKey: ["training-record-options"],
    queryFn: () => getList<TrainingRecord>("/training-records/", { page_size: 150 }),
  });

  const issue = useMutation({
    mutationFn: (trainingRecord: number) =>
      request<Certificate>("/certificates/issue/", {
        method: "POST",
        body: JSON.stringify({ training_record: trainingRecord }),
      }),
    onSuccess: (certificate) => {
      void queryClient.invalidateQueries({ queryKey: ["certificates"] });
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      toast.push(`Certificate ${certificate.certificate_no} issued.`);
      onClose();
    },
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    issue.mutate(Number(record));
  }

  return (
    <Modal
      open
      onClose={onClose}
      title="Issue a certificate"
      description="Number allocation, age checks and medical validity are enforced by the server."
      footer={
        <>
          <Button onClick={onClose}>Cancel</Button>
          <Button type="submit" form="issue-form" variant="primary" busy={issue.isPending}>
            Issue certificate
          </Button>
        </>
      }
    >
      <form id="issue-form" className="form-stack" onSubmit={submit}>
        {issue.isError ? (
          <div className="form-error" role="alert">
            {errorMessage(issue.error)}
          </div>
        ) : null}
        <Field
          label="Training record"
          htmlFor="certificate-record"
          hint="Choose the completed training record behind this certificate."
        >
          <Select
            id="certificate-record"
            required
            value={record}
            onChange={(event) => setRecord(event.target.value)}
          >
            <option value="">
              {records.isLoading ? "Loading records…" : "Choose a training record"}
            </option>
            {(records.data?.data ?? []).map((row) => (
              <option value={row.id} key={row.id}>
                {row.learner_name} · {row.course_code} · {row.status_code} · {formatDate(row.start_date)}
              </option>
            ))}
          </Select>
        </Field>
      </form>
    </Modal>
  );
}

function IdCardPanel({
  certificate,
  canManage,
  canPrint,
}: {
  certificate: Certificate;
  canManage: boolean;
  canPrint: boolean;
}) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const cards = useQuery({
    queryKey: ["id-cards", certificate.training_record],
    queryFn: () =>
      getList<IDCard>("/id-cards/", {
        training_record: certificate.training_record,
        page_size: 10,
      }),
  });
  const card = cards.data?.data[0];
  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: ["id-cards", certificate.training_record] });
    void queryClient.invalidateQueries({ queryKey: ["certificates"] });
  };
  const issue = useMutation({
    mutationFn: () =>
      request<IDCard>("/id-cards/issue/", {
        method: "POST",
        body: JSON.stringify({ training_record: certificate.training_record }),
      }),
    onSuccess: () => {
      refresh();
      toast.push("ID card record created.");
    },
  });
  const generate = useMutation({
    mutationFn: () =>
      request<IDCard>(`/id-cards/${card?.id}/generate/`, {
        method: "POST",
        body: JSON.stringify({}),
      }),
    onSuccess: () => {
      refresh();
      toast.push("ID card PDF generated.");
    },
  });
  const print = useMutation({
    mutationFn: () =>
      request<IDCard>(`/id-cards/${card?.id}/print/`, {
        method: "POST",
        body: JSON.stringify({}),
      }),
    onSuccess: () => {
      refresh();
      toast.push("ID card marked as printed.");
    },
  });
  const download = () => {
    if (!card) return;
    void downloadFile(`/id-cards/${card.id}/document/`, `${card.card_no}.pdf`).catch((error) =>
      toast.push(errorMessage(error), "error"),
    );
  };

  return (
    <div className="form-stack">
      <h3>ID card</h3>
      {cards.isLoading ? <p className="hint">Loading ID card…</p> : null}
      {!cards.isLoading && !card ? (
        canManage ? (
          <Button busy={issue.isPending} onClick={() => issue.mutate()}>
            <CreditCard size={16} aria-hidden="true" /> Issue ID card
          </Button>
        ) : (
          <p className="hint">No ID card has been issued for this record.</p>
        )
      ) : null}
      {card ? (
        <>
          <p className="hint">
            Card <span className="mono">{card.card_no}</span>{" "}
            {card.printed_at ? `· printed ${formatDate(card.printed_at)}` : "· not printed"}
          </p>
          <div className="row-actions">
            <Button size="sm" onClick={download}>
              <Download size={14} aria-hidden="true" /> Download
            </Button>
            {canManage ? (
              <Button size="sm" busy={generate.isPending} onClick={() => generate.mutate()}>
                <CreditCard size={14} aria-hidden="true" /> Generate / reprint
              </Button>
            ) : null}
            {canPrint ? (
              <Button
                size="sm"
                busy={print.isPending}
                disabled={Boolean(card.printed_at)}
                onClick={() => print.mutate()}
              >
                <Printer size={14} aria-hidden="true" /> Mark printed
              </Button>
            ) : null}
          </div>
        </>
      ) : null}
      {issue.isError || generate.isError || print.isError ? (
        <div className="form-error" role="alert">
          {errorMessage(issue.error ?? generate.error ?? print.error)}
        </div>
      ) : null}
    </div>
  );
}

function CertificateDocumentsModal({
  certificate,
  canManage,
  canPrint,
  onClose,
}: {
  certificate: Certificate;
  canManage: boolean;
  canPrint: boolean;
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [current, setCurrent] = useState(certificate);
  const [file, setFile] = useState<File | null>(null);
  const [certNo, setCertNo] = useState(certificate.certificate_no);
  const [learnerId, setLearnerId] = useState(certificate.opito_learner_id);
  const isOpito = current.format === 4;

  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: ["certificates"] });
    void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
  };
  const generate = useMutation({
    mutationFn: () =>
      request<Certificate>(`/certificates/${current.id}/generate/`, {
        method: "POST",
        body: JSON.stringify({}),
      }),
    onSuccess: (data) => {
      setCurrent(data);
      refresh();
      toast.push("Certificate PDF generated.");
    },
  });
  const upload = useMutation({
    mutationFn: async () => {
      if (!file) throw new Error("Choose a PDF file to upload.");
      const form = new FormData();
      form.append("file", file);
      if (certNo) form.append("certificate_no", certNo);
      if (learnerId) form.append("opito_learner_id", learnerId);
      return request<Certificate>(`/certificates/${current.id}/upload/`, {
        method: "POST",
        body: form,
      });
    },
    onSuccess: (data) => {
      setCurrent(data);
      setFile(null);
      refresh();
      toast.push("Certificate PDF uploaded.");
    },
  });
  const print = useMutation({
    mutationFn: () =>
      request<Certificate>(`/certificates/${current.id}/print/`, {
        method: "POST",
        body: JSON.stringify({}),
      }),
    onSuccess: (data) => {
      setCurrent(data);
      refresh();
      toast.push("Certificate marked as printed.");
    },
  });
  const download = () => {
    void downloadFile(
      `/certificates/${current.id}/document/`,
      `${current.certificate_no}.pdf`,
    ).catch((error) => toast.push(errorMessage(error), "error"));
  };

  return (
    <Modal
      open
      onClose={onClose}
      title={`Files · ${current.certificate_no}`}
      description="Generated PDFs are stored once and reused for staff and learner downloads."
      footer={<Button onClick={onClose}>Close</Button>}
    >
      <div className="form-stack">
        <div className="row-actions">
          <Button onClick={download}>
            <Download size={16} aria-hidden="true" /> Download certificate
          </Button>
          {canManage && !isOpito ? (
            <Button busy={generate.isPending} onClick={() => generate.mutate()}>
              <Award size={16} aria-hidden="true" /> Generate / re-generate
            </Button>
          ) : null}
          {canPrint ? (
            <Button
              busy={print.isPending}
              disabled={Boolean(current.printed_at)}
              onClick={() => print.mutate()}
            >
              <Printer size={16} aria-hidden="true" /> Mark printed
            </Button>
          ) : null}
        </div>

        {canManage && isOpito ? (
          <div className="form-stack">
            <p className="hint">
              OPITO certificates are issued externally. Upload the signed PDF and record the
              learner and certificate numbers.
            </p>
            <Field label="Certificate PDF" htmlFor="certificate-file">
              <Input
                id="certificate-file"
                type="file"
                accept="application/pdf"
                onChange={(event) => setFile(event.target.files?.[0] ?? null)}
              />
            </Field>
            <Field label="OPITO certificate number" htmlFor="certificate-number">
              <Input
                id="certificate-number"
                value={certNo}
                onChange={(event) => setCertNo(event.target.value)}
              />
            </Field>
            <Field label="OPITO learner ID" htmlFor="opito-learner-id">
              <Input
                id="opito-learner-id"
                value={learnerId}
                onChange={(event) => setLearnerId(event.target.value)}
              />
            </Field>
            <Button
              variant="primary"
              busy={upload.isPending}
              disabled={!file}
              onClick={() => upload.mutate()}
            >
              <Upload size={16} aria-hidden="true" /> Upload certificate
            </Button>
          </div>
        ) : null}

        {generate.isError || upload.isError || print.isError ? (
          <div className="form-error" role="alert">
            {errorMessage(generate.error ?? upload.error ?? print.error)}
          </div>
        ) : null}

        {current.course_id_card ? (
          <IdCardPanel
            certificate={current}
            canManage={canManage}
            canPrint={canPrint}
          />
        ) : null}
      </div>
    </Modal>
  );
}

export function CertificatesPage() {
  const { user } = useAuth();
  const toast = useToast();
  const queryClient = useQueryClient();
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  const [issuing, setIssuing] = useState(false);
  const [documents, setDocuments] = useState<Certificate | null>(null);
  const [pendingAction, setPendingAction] = useState<{
    certificate: Certificate;
    action: "md-approve" | "release" | "renew";
  } | null>(null);
  const search = useDebounced(query);

  const certificates = useQuery({
    queryKey: ["certificates", search, page],
    queryFn: () =>
      getList<Certificate>("/certificates/", {
        search,
        page,
        page_size: 25,
      }),
  });

  const action = useMutation({
    mutationFn: ({
      certificate,
      name,
    }: {
      certificate: Certificate;
      name: "md-approve" | "release" | "renew";
    }) =>
      request<unknown>(`/certificates/${certificate.id}/${name}/`, {
        method: "POST",
        body: JSON.stringify({}),
      }),
    onSuccess: (_data, variables) => {
      void queryClient.invalidateQueries({ queryKey: ["certificates"] });
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      void queryClient.invalidateQueries({ queryKey: ["enrolments"] });
      toast.push(
        variables.name === "md-approve"
          ? "Signature and seal applied."
          : variables.name === "release"
            ? "Certificate released and reminders scheduled."
            : "Renewal requested.",
      );
      setPendingAction(null);
    },
  });

  if (certificates.isLoading) return <Loading rows={7} />;
  if (certificates.isError || !certificates.data) {
    return (
      <ErrorState
        message={errorMessage(certificates.error)}
        retry={() => void certificates.refetch()}
      />
    );
  }

  const canIssue = can(user, CERTIFICATE_ISSUE);
  const canPrint = can(user, CERTIFICATE_PRINT);
  const canSign = can(user, CERTIFICATE_MD);
  const canRelease = can(user, CERTIFICATE_RELEASE);

  return (
    <>
      <PageHeader
        eyebrow="Certification"
        title="Certificates"
        description="Issued, signed and released certificates, with renewal requests in one trail."
        actions={
          <>
            <CsvButton dataset="certificates" label="Export certificates" />
            {canIssue ? (
              <Button variant="primary" onClick={() => setIssuing(true)}>
                <Award size={16} aria-hidden="true" /> Issue certificate
              </Button>
            ) : null}
          </>
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
            placeholder="Search certificate no, badge or surname"
          />
          <span className="toolbar-count">{certificates.data.total} certificates</span>
        </Toolbar>

        {certificates.data.data.length ? (
          <>
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Certificate</th>
                    <th>Learner</th>
                    <th>Course</th>
                    <th>Issued</th>
                    <th>Expiry</th>
                    <th>State</th>
                    <th aria-label="Actions" />
                  </tr>
                </thead>
                <tbody>
                  {certificates.data.data.map((certificate) => {
                    const state = certificateState(certificate);
                    return (
                      <tr key={certificate.id}>
                        <td className="mono">{certificate.certificate_no}</td>
                        <td>
                          <strong>{certificate.learner_name}</strong>
                          <div className="cell-sub mono">{certificate.badge_no}</div>
                        </td>
                        <td className="mono">{certificate.course_code || "—"}</td>
                        <td>{formatDate(certificate.issued_at)}</td>
                        <td>{formatDate(certificate.expiry_date)}</td>
                        <td>
                          <Badge tone={state.tone}>{state.label}</Badge>
                        </td>
                        <td className="row-actions">
                          <Button size="sm" onClick={() => setDocuments(certificate)}>
                            <Download size={14} aria-hidden="true" /> Files
                          </Button>
                          {canSign &&
                          !certificate.md_approved_at &&
                          !certificate.voided_at ? (
                            <Button
                              size="sm"
                              onClick={() => setPendingAction({ certificate, action: "md-approve" })}
                            >
                              <PenLine size={14} aria-hidden="true" /> Sign
                            </Button>
                          ) : null}
                          {canRelease &&
                          certificate.md_approved_at &&
                          !certificate.released_at &&
                          !certificate.voided_at ? (
                            <Button
                              size="sm"
                              onClick={() => setPendingAction({ certificate, action: "release" })}
                            >
                              <Send size={14} aria-hidden="true" /> Release
                            </Button>
                          ) : null}
                          {certificate.released_at &&
                          !certificate.voided_at &&
                          !certificate.renewed_by_certificate ? (
                            <Button
                              size="sm"
                              onClick={() => setPendingAction({ certificate, action: "renew" })}
                            >
                              <RotateCcw size={14} aria-hidden="true" /> Renew
                            </Button>
                          ) : null}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <Pagination
              page={certificates.data.page}
              pageSize={certificates.data.page_size}
              total={certificates.data.total}
              onPage={setPage}
            />
          </>
        ) : (
          <EmptyState
            title="No certificates found"
            body={
              query
                ? "No certificate matches this search."
                : "Issue the first certificate from a completed training record."
            }
            action={
              canIssue && !query ? (
                <Button variant="primary" onClick={() => setIssuing(true)}>
                  Issue certificate
                </Button>
              ) : undefined
            }
          />
        )}
      </Card>

      <ConfirmDialog
        open={Boolean(pendingAction)}
        title={
          pendingAction?.action === "md-approve"
            ? "Apply signature and seal"
            : pendingAction?.action === "release"
              ? "Release certificate"
              : "Request renewal"
        }
        message={
          pendingAction?.action === "md-approve"
            ? `Sign and seal ${pendingAction.certificate.certificate_no} on behalf of the Managing Director?`
            : pendingAction?.action === "release"
              ? `Release ${pendingAction?.certificate.certificate_no ?? ""} to the learner and schedule expiry reminders?`
              : `Create a renewal training record for ${pendingAction?.certificate.learner_name ?? ""}? This uses the next available session or the refresher course.`
        }
        confirmLabel={
          pendingAction?.action === "md-approve"
            ? "Apply signature"
            : pendingAction?.action === "release"
              ? "Release"
              : "Request renewal"
        }
        busy={action.isPending}
        onConfirm={() => {
          if (pendingAction) {
            action.mutate({
              certificate: pendingAction.certificate,
              name: pendingAction.action,
            });
          }
        }}
        onClose={() => setPendingAction(null)}
      />
      {action.isError ? (
        <div className="form-error floating-error" role="alert">
          {errorMessage(action.error)}
        </div>
      ) : null}

      {issuing ? <IssueEditor onClose={() => setIssuing(false)} /> : null}
      {documents ? (
        <CertificateDocumentsModal
          certificate={documents}
          canManage={canIssue}
          canPrint={canPrint}
          onClose={() => setDocuments(null)}
        />
      ) : null}
    </>
  );
}
