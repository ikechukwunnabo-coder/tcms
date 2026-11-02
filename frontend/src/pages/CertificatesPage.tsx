import { useState } from "react";
import type { FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Award, PenLine, RotateCcw, Send } from "lucide-react";
import { getList, request } from "../api/client";
import type { Certificate, TrainingRecord } from "../api/types";
import { useAuth } from "../auth/context";
import {
  CERTIFICATE_ISSUE,
  CERTIFICATE_MD,
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

export function CertificatesPage() {
  const { user } = useAuth();
  const toast = useToast();
  const queryClient = useQueryClient();
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  const [issuing, setIssuing] = useState(false);
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
    </>
  );
}
