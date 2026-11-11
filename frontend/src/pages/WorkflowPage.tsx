import { useState } from "react";
import type { FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router-dom";
import { ArrowRight, CornerUpLeft, GitPullRequest, XCircle } from "lucide-react";
import { getList, request } from "../api/client";
import type { Dashboard, TrainingRecord } from "../api/types";
import { useAuth } from "../auth/context";
import { roleLabelById } from "../auth/roles";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorState,
  Field,
  Loading,
  Modal,
  PageHeader,
  Pagination,
  SearchInput,
  Select,
  Textarea,
  Toolbar,
} from "../components/ui";
import { useToast } from "../components/toastContext";
import { count, errorMessage, formatDate } from "../lib/format";
import { useDebounced } from "../lib/hooks";

function ActionEditor({
  record,
  action,
  onClose,
}: {
  record: TrainingRecord;
  action: "approve" | "reject" | "cancel";
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [reason, setReason] = useState("");

  const submitAction = useMutation({
    mutationFn: () =>
      request<{ status: number; code: string }>(`/approvals/${record.id}/advance/`, {
        method: "POST",
        body: JSON.stringify({ action, reason }),
      }),
    onSuccess: (result) => {
      void queryClient.invalidateQueries({ queryKey: ["training-records"] });
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      toast.push(`Record moved to ${result.code.replace(/_/g, " ")}.`);
      onClose();
    },
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    if (action === "reject" && !reason.trim()) return;
    submitAction.mutate();
  }

  return (
    <Modal
      open
      onClose={onClose}
      title={
        action === "approve"
          ? "Advance training record"
          : action === "reject"
            ? "Reject training record"
            : "Cancel training record"
      }
      description={`${record.learner_name} · ${record.course_code} · ${record.status_code}`}
      footer={
        <>
          <Button onClick={onClose}>Back</Button>
          <Button
            type="submit"
            form="workflow-action-form"
            variant={action === "approve" ? "primary" : "danger"}
            busy={submitAction.isPending}
            disabled={action === "reject" && !reason.trim()}
          >
            {action === "approve" ? "Advance" : action === "reject" ? "Reject" : "Cancel record"}
          </Button>
        </>
      }
    >
      <form id="workflow-action-form" className="form-stack" onSubmit={submit}>
        {submitAction.isError ? (
          <div className="form-error" role="alert">
            {errorMessage(submitAction.error)}
          </div>
        ) : null}
        <Field
          label={action === "reject" ? "Rejection reason" : "Note (optional)"}
          htmlFor="workflow-reason"
          hint={
            action === "reject"
              ? "The reason is shown to the previous stage for correction."
              : "Record any context for the audit trail."
          }
        >
          <Textarea
            id="workflow-reason"
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

export function WorkflowPage() {
  const { user } = useAuth();
  const [params, setParams] = useSearchParams();
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  const [pending, setPending] = useState<{
    record: TrainingRecord;
    action: "approve" | "reject" | "cancel";
  } | null>(null);
  const search = useDebounced(query);
  const status = params.get("status") ?? "";

  const dashboard = useQuery({
    queryKey: ["dashboard"],
    queryFn: () => request<Dashboard>("/dashboard/"),
  });

  const records = useQuery({
    queryKey: ["training-records", search, status, page],
    queryFn: () =>
      getList<TrainingRecord>("/training-records/", {
        search,
        status,
        page,
        page_size: 25,
      }),
  });

  if (records.isLoading) return <Loading rows={7} />;
  if (records.isError || !records.data) {
    return <ErrorState message={errorMessage(records.error)} retry={() => void records.refetch()} />;
  }

  const workflow = dashboard.data?.workflow ?? [];
  const statusById = new Map(workflow.map((row) => [row.status, row]));
  const selectedStatus = status ? statusById.get(Number(status)) : undefined;

  function selectStatus(value: string) {
    const next = new URLSearchParams();
    if (value) next.set("status", value);
    setParams(next);
    setPage(1);
  }

  const canActOn = (record: TrainingRecord) => {
    if (record.status_code === "rejected" || record.status_code === "id_card_done") return true;
    const nextRole = statusById.get(record.status)?.next_role;
    if (!nextRole) return false;
    return Boolean(user?.roles.includes(nextRole) || user?.role_codes.includes("system_admin"));
  };

  return (
    <>
      <PageHeader
        eyebrow="Operations"
        title="All Training Records"
        description="Manage and view all existing training records in the database. Every workflow transition is attributed."
      />

      {workflow.length ? (
        <Card className="stage-card">
          <div className="stage-rail">
            {workflow.map((stage) => (
              <button
                type="button"
                key={stage.status}
                className={`stage-tile ${status === String(stage.status) ? "active" : ""} ${
                  stage.count ? "has-work" : ""
                }`}
                onClick={() => selectStatus(status === String(stage.status) ? "" : String(stage.status))}
              >
                <span>{stage.name}</span>
                <strong>{count(stage.count)}</strong>
                <small>{stage.terminal ? "Terminal" : roleLabelById(stage.next_role)}</small>
              </button>
            ))}
          </div>
        </Card>
      ) : null}

      <Card>
        <Toolbar>
          <SearchInput
            value={query}
            onChange={(value) => {
              setQuery(value);
              setPage(1);
            }}
            placeholder="Search badge, surname or course code"
          />
          <Select
            aria-label="Filter by workflow stage"
            value={status}
            onChange={(event) => selectStatus(event.target.value)}
          >
            <option value="">All stages</option>
            {workflow.map((stage) => (
              <option value={stage.status} key={stage.status}>
                {stage.name} ({count(stage.count)})
              </option>
            ))}
          </Select>
          {selectedStatus ? (
            <Badge tone="brand">
              {selectedStatus.name} · {roleLabelById(selectedStatus.next_role)}
            </Badge>
          ) : null}
          <span className="toolbar-count">{records.data.total} records</span>
        </Toolbar>

        {records.data.data.length ? (
          <>
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Record</th>
                    <th>Learner</th>
                    <th>Course</th>
                    <th>Dates</th>
                    <th>Stage</th>
                    <th>Next role</th>
                    <th aria-label="Actions" />
                  </tr>
                </thead>
                <tbody>
                  {records.data.data.map((record) => {
                    const stage = statusById.get(record.status);
                    const actionable = canActOn(record);
                    return (
                      <tr key={record.id}>
                        <td className="mono">TR-{record.id}</td>
                        <td>
                          <strong>{record.learner_name}</strong>
                          <div className="cell-sub mono">{record.badge_no}</div>
                        </td>
                        <td>
                          <strong className="mono">{record.course_code}</strong>
                          <div className="cell-sub">{record.session ? `Session #${record.session}` : "No session"}</div>
                        </td>
                        <td>
                          {formatDate(record.start_date)}
                          <div className="cell-sub">
                            {record.end_date ? `to ${formatDate(record.end_date)}` : "Open"}
                          </div>
                        </td>
                        <td>
                          <StatusStage code={record.status_code} name={stage?.name} />
                          {record.reject_reason ? (
                            <div className="cell-sub danger-text">{record.reject_reason}</div>
                          ) : null}
                        </td>
                        <td>{stage?.terminal ? "—" : roleLabelById(stage?.next_role)}</td>
                        <td className="row-actions">
                          <Link className="btn btn-ghost btn-sm" to={`/training-records/${record.id}`}>
                            Open
                          </Link>
                          {actionable ? (
                            <>
                              <Button
                                size="sm"
                                variant="primary"
                                onClick={() => setPending({ record, action: "approve" })}
                              >
                                {record.status_code === "rejected" ? (
                                  <>
                                    <CornerUpLeft size={14} aria-hidden="true" /> Re-enter
                                  </>
                                ) : (
                                  <>
                                    <ArrowRight size={14} aria-hidden="true" /> Advance
                                  </>
                                )}
                              </Button>
                              {record.status_code !== "rejected" ? (
                                <Button
                                  size="sm"
                                  variant="danger"
                                  onClick={() => setPending({ record, action: "reject" })}
                                >
                                  <XCircle size={14} aria-hidden="true" /> Reject
                                </Button>
                              ) : null}
                            </>
                          ) : (
                            <span className="muted small">
                              {stage?.terminal ? "Closed" : "Awaiting another role"}
                            </span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <Pagination
              page={records.data.page}
              pageSize={records.data.page_size}
              total={records.data.total}
              onPage={setPage}
            />
          </>
        ) : (
          <EmptyState
            title="No training records"
            body={
              search || status
                ? "No record matches the current stage or search."
                : "Training records appear here once enrolments are confirmed and delivery begins."
            }
          />
        )}
      </Card>

      {pending ? (
        <ActionEditor
          record={pending.record}
          action={pending.action}
          onClose={() => setPending(null)}
        />
      ) : null}
    </>
  );
}

function StatusStage({ code, name }: { code: string; name?: string }) {
  const tone = code === "rejected" ? "danger" : code === "completed" ? "ok" : "warn";
  return (
    <Badge tone={tone}>
      <GitPullRequest size={12} aria-hidden="true" /> {name ?? code.replace(/_/g, " ")}
    </Badge>
  );
}
