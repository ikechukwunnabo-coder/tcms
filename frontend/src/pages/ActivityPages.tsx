import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import {
  ArrowRight,
  CalendarDays,
  Check,
  ClipboardCheck,
  History,
  XCircle,
} from "lucide-react";
import { getList, request } from "../api/client";
import type { BulkActionResult, MyActivity, TrainingRecord } from "../api/types";
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
  Pagination,
  SearchInput,
  Select,
  StatusBadge,
  Textarea,
  Toolbar,
} from "../components/ui";
import { useToast } from "../components/toastContext";
import { count, errorMessage, formatDate, formatDateTime, titleCase } from "../lib/format";
import { useDebounced } from "../lib/hooks";

function stageLabel(value: string) {
  const label = value.replace(/_/g, " ");
  return label.charAt(0).toUpperCase() + label.slice(1);
}

function dateRange(record: TrainingRecord) {
  const start = formatDate(record.start_date);
  const end = formatDate(record.end_date);
  if (start === "-") return "-";
  return end !== "-" && end !== start ? `${start} - ${end}` : start;
}

function ActivityAction({
  record,
  action,
  onDone,
}: {
  record: TrainingRecord;
  action: "approve" | "reject";
  onDone: () => void;
}) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const mutation = useMutation({
    mutationFn: () =>
      request<{ status: number; code: string }>(`/approvals/${record.id}/advance/`, {
        method: "POST",
        body: JSON.stringify({
          action,
          reason: action === "reject" ? "Returned from the task queue." : "",
        }),
      }),
    onSuccess: (result) => {
      void queryClient.invalidateQueries({ queryKey: ["my-activity"] });
      void queryClient.invalidateQueries({ queryKey: ["training-records"] });
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      toast.push(`TR-${record.id} moved to ${result.code.replace(/_/g, " ")}.`);
      onDone();
    },
  });

  return (
    <Button
      size="sm"
      variant={action === "approve" ? "secondary" : "danger"}
      busy={mutation.isPending}
      onClick={() => mutation.mutate()}
      aria-label={`${action === "approve" ? "Approve" : "Reject"} TR-${record.id}`}
    >
      {action === "approve" ? <Check size={14} aria-hidden="true" /> : <XCircle size={14} aria-hidden="true" />}
      {action === "approve" ? "Approve" : "Reject"}
    </Button>
  );
}

function RecordRow({
  record,
  actions,
  onDone,
}: {
  record: TrainingRecord;
  actions?: boolean;
  onDone: () => void;
}) {
  return (
    <tr>
      <td className="mono">TR-{record.id}</td>
      <td>
        <Link className="table-link" to={`/learners/${record.learner}`}>
          <strong>{record.learner_name}</strong>
        </Link>
        <div className="cell-sub mono">{record.badge_no}</div>
      </td>
      <td>
        <strong className="mono">{record.course_code}</strong>
        <div className="cell-sub">{formatDate(record.start_date)}</div>
      </td>
      <td>
        <StatusBadge status={record.status_code} />
      </td>
      <td>
        <div className="row-actions">
          {actions ? (
            <>
              <ActivityAction record={record} action="approve" onDone={onDone} />
              <ActivityAction record={record} action="reject" onDone={onDone} />
            </>
          ) : null}
          <Link className="btn btn-ghost btn-sm" to={`/training-records/${record.id}`}>
            Open <ArrowRight size={14} aria-hidden="true" />
          </Link>
        </div>
      </td>
    </tr>
  );
}

function PendingTable({
  records,
  actions,
  onRefresh,
}: {
  records: TrainingRecord[];
  actions?: boolean;
  onRefresh: () => void;
}) {
  if (!records.length) {
    return (
      <EmptyState
        title="Nothing waiting on you"
        body="There are no training records at a stage assigned to your role right now."
      />
    );
  }
  return (
    <div className="table-wrap">
      <table className="table">
        <thead>
          <tr>
            <th>Record</th>
            <th>Learner</th>
            <th>Course</th>
            <th>Stage</th>
            <th aria-label="Actions" />
          </tr>
        </thead>
        <tbody>
          {records.map((record) => (
            <RecordRow
              key={record.id}
              record={record}
              actions={actions}
              onDone={onRefresh}
            />
          ))}
        </tbody>
      </table>
    </div>
  );
}

function useActivity() {
  return useQuery({
    queryKey: ["my-activity"],
    queryFn: () => request<MyActivity>("/approvals/my-activity/"),
    refetchInterval: 60_000,
  });
}

export function PendingTasksPage() {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [query, setQuery] = useState("");
  const [date, setDate] = useState("");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [rejecting, setRejecting] = useState(false);
  const [reason, setReason] = useState("");
  const search = useDebounced(query);

  const pending = useQuery({
    queryKey: ["pending-tasks", search, date, page, pageSize],
    queryFn: () =>
      getList<TrainingRecord>("/approvals/pending-tasks/", {
        search,
        date,
        page,
        page_size: pageSize,
      }),
    refetchInterval: 60_000,
  });

  const bulk = useMutation({
    mutationFn: (action: "approve" | "reject") =>
      request<BulkActionResult>("/approvals/bulk/", {
        method: "POST",
        body: JSON.stringify({ ids: [...selected], action, reason }),
      }),
    onSuccess: (result) => {
      void queryClient.invalidateQueries({ queryKey: ["pending-tasks"] });
      void queryClient.invalidateQueries({ queryKey: ["my-activity"] });
      void queryClient.invalidateQueries({ queryKey: ["training-records"] });
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      toast.push(
        `${result.succeeded} record${result.succeeded === 1 ? "" : "s"} updated` +
          (result.failed ? `, ${result.failed} failed.` : "."),
      );
      setSelected(new Set());
      setRejecting(false);
      setReason("");
      setPage(1);
    },
  });

  const rows = pending.data?.data ?? [];
  const pageIds = rows.map((record) => record.id);
  const allSelected = pageIds.length > 0 && pageIds.every((id) => selected.has(id));

  function resetSelection() {
    setSelected(new Set());
    setPage(1);
  }

  function toggleAll() {
    setSelected((current) => {
      const next = new Set(current);
      if (allSelected) pageIds.forEach((id) => next.delete(id));
      else pageIds.forEach((id) => next.add(id));
      return next;
    });
  }

  function toggleOne(id: number) {
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function rejectSelected() {
    if (!reason.trim() || !selected.size) return;
    bulk.mutate("reject");
  }

  return (
    <>
      <PageHeader
        eyebrow="My work"
        title="My Pending Tasks"
        description="Act on the pending tasks related to your Role by approving, rejecting or updating training data."
        actions={
          <Badge tone={pending.data?.total ? "warn" : "ok"}>
            {count(pending.data?.total ?? 0)} records
          </Badge>
        }
      />
      <Card>
        <Toolbar>
          <div className="task-date-filter">
            <CalendarDays size={16} aria-hidden="true" />
            <Input
              type="date"
              value={date}
              aria-label="Filter pending tasks by date"
              onChange={(event) => {
                setDate(event.target.value);
                resetSelection();
              }}
            />
            <span className="muted">{date ? formatDate(date) : "No date selected"}</span>
            {date ? (
              <button
                type="button"
                className="text-link"
                onClick={() => {
                  setDate("");
                  resetSelection();
                }}
              >
                Clear
              </button>
            ) : null}
          </div>
          <div className="task-select-actions">
            <button type="button" className="text-link" onClick={toggleAll}>
              Select all
            </button>
            <span aria-hidden="true">·</span>
            <button
              type="button"
              className="text-link"
              onClick={() => setSelected(new Set())}
            >
              Select none
            </button>
          </div>
          <SearchInput
            value={query}
            onChange={(value) => {
              setQuery(value);
              resetSelection();
            }}
            placeholder="Search record, learner, company or course"
          />
          <span className="toolbar-count">{count(pending.data?.total ?? 0)} found</span>
        </Toolbar>

        {selected.size ? (
          <div className="task-bulk-bar">
            <strong>{selected.size} selected</strong>
            <Button
              size="sm"
              variant="primary"
              busy={bulk.isPending && !rejecting}
              onClick={() => {
                bulk.reset();
                bulk.mutate("approve");
              }}
            >
              <Check size={14} aria-hidden="true" /> Approve selected
            </Button>
            <Button
              size="sm"
              variant="danger"
              onClick={() => {
                bulk.reset();
                setReason("");
                setRejecting(true);
              }}
            >
              <XCircle size={14} aria-hidden="true" /> Return selected
            </Button>
          </div>
        ) : null}

        {bulk.isError && !rejecting ? (
          <div className="form-error" role="alert">
            {errorMessage(bulk.error)}
          </div>
        ) : null}

        {pending.isLoading ? (
          <Loading rows={7} />
        ) : pending.isError || !pending.data ? (
          <ErrorState
            message={errorMessage(pending.error)}
            retry={() => void pending.refetch()}
          />
        ) : rows.length ? (
          <>
            <div className="table-wrap">
              <table className="table task-table">
                <thead>
                  <tr>
                    <th className="check-cell">
                      <input
                        type="checkbox"
                        checked={allSelected}
                        onChange={toggleAll}
                        aria-label="Select all records on this page"
                      />
                    </th>
                    <th>Training record</th>
                    <th>Course</th>
                    <th>Dates</th>
                    <th>Learner</th>
                    <th>Company</th>
                    <th>Stage</th>
                    <th className="num">ID</th>
                    <th aria-label="Actions" />
                  </tr>
                </thead>
                <tbody>
                  {rows.map((record) => (
                    <tr
                      key={record.id}
                      className={selected.has(record.id) ? "selected" : undefined}
                    >
                      <td className="check-cell">
                        <input
                          type="checkbox"
                          checked={selected.has(record.id)}
                          onChange={() => toggleOne(record.id)}
                          aria-label={`Select TR-${record.id}`}
                        />
                      </td>
                      <td className="mono">
                        <Link className="table-link" to={`/training-records/${record.id}`}>
                          TR-{record.id}
                        </Link>
                      </td>
                      <td>
                        <strong>{record.course_name}</strong>
                        <div className="cell-sub mono">{record.course_code}</div>
                      </td>
                      <td className="task-date-cell">{dateRange(record)}</td>
                      <td>
                        <Link className="table-link" to={`/learners/${record.learner}`}>
                          <strong>{record.learner_name}</strong>
                        </Link>
                        <div className="cell-sub mono">{record.badge_no}</div>
                      </td>
                      <td>{record.company_name || "Individual"}</td>
                      <td>
                        <Badge tone="neutral">{stageLabel(record.status_code)}</Badge>
                      </td>
                      <td className="num mono">{record.id}</td>
                      <td>
                        <div className="row-actions">
                          <Link
                            className="btn btn-ghost btn-sm"
                            to={`/training-records/${record.id}`}
                          >
                            Open <ArrowRight size={14} aria-hidden="true" />
                          </Link>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="task-page-size">
              <span>{count(pending.data.total)} records found</span>
              <label>
                Show
                <Select
                  value={pageSize}
                  aria-label="Records per page"
                  onChange={(event) => {
                    setPageSize(Number(event.target.value));
                    resetSelection();
                  }}
                >
                  <option value={20}>20</option>
                  <option value={50}>50</option>
                  <option value={100}>100</option>
                </Select>
                per page
              </label>
            </div>
            <Pagination
              page={pending.data.page}
              pageSize={pending.data.page_size}
              total={pending.data.total}
              onPage={(next) => {
                setPage(next);
                setSelected(new Set());
              }}
            />
          </>
        ) : (
          <EmptyState
            title="Nothing waiting on you"
            body={
              search || date
                ? "No pending task matches the current search or date."
                : "There are no training records at a stage assigned to your role right now."
            }
          />
        )}
      </Card>

      <Modal
        open={rejecting}
        onClose={() => {
          bulk.reset();
          setRejecting(false);
        }}
        title={`Return ${selected.size} selected record${selected.size === 1 ? "" : "s"}`}
        description="The records will move back for correction. The reason is shown to the previous stage."
        footer={
          <>
            <Button
              onClick={() => {
                bulk.reset();
                setRejecting(false);
              }}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              form="bulk-reject-form"
              variant="danger"
              busy={bulk.isPending}
              disabled={!reason.trim()}
            >
              Return selected
            </Button>
          </>
        }
      >
        <form
          id="bulk-reject-form"
          className="form-stack"
          onSubmit={(event) => {
            event.preventDefault();
            rejectSelected();
          }}
        >
          {bulk.isError ? (
            <div className="form-error" role="alert">
              {errorMessage(bulk.error)}
            </div>
          ) : null}
          <Field
            label="Reason"
            htmlFor="bulk-reject-reason"
            hint="Required so the previous stage knows what to correct."
          >
            <Textarea
              id="bulk-reject-reason"
              rows={3}
              required
              value={reason}
              onChange={(event) => setReason(event.target.value)}
            />
          </Field>
        </form>
      </Modal>
    </>
  );
}

export function MyActivityPage() {
  const activity = useActivity();
  if (activity.isLoading) return <Loading rows={7} />;
  if (activity.isError || !activity.data) {
    return (
      <ErrorState
        message={errorMessage(activity.error)}
        retry={() => void activity.refetch()}
      />
    );
  }

  return (
    <>
      <PageHeader
        eyebrow="My work"
        title="My activity"
        description="A personal audit trail of workflow decisions, alongside the records still waiting on you."
        actions={
          <Badge tone="brand">
            {count(activity.data.recent.length)} recent
          </Badge>
        }
      />
      <div className="split-grid">
        <Card
          title="Still waiting"
          aside={
            <Link className="text-link" to="/tasks">
              <ClipboardCheck size={14} aria-hidden="true" /> Task queue
            </Link>
          }
        >
          <PendingTable
            records={activity.data.pending}
            onRefresh={() => void activity.refetch()}
          />
        </Card>
        <Card
          title="Recent decisions"
          aside={<History size={15} aria-hidden="true" />}
        >
          {activity.data.recent.length ? (
            <ul className="timeline">
              {activity.data.recent.map((row) => (
                <li key={row.id}>
                  <span className={`timeline-mark ${row.action === "reject" ? "danger" : "ok"}`}>
                    {row.action === "reject" ? (
                      <XCircle size={14} aria-hidden="true" />
                    ) : (
                      <Check size={14} aria-hidden="true" />
                    )}
                  </span>
                  <div>
                    <strong>
                      {titleCase(row.action)} A· TR-{row.training_record}
                    </strong>
                    <p>
                      <Link to={`/training-records/${row.training_record}`}>
                        {row.record.learner_name}
                      </Link>{" "}
                      A· {row.record.course_code}
                    </p>
                    <small>{formatDateTime(row.acted_at)}</small>
                    {row.reason ? <p className="timeline-note">{row.reason}</p> : null}
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <EmptyState
              title="No decisions yet"
              body="Approvals and rejections you make will be recorded here with their reason."
            />
          )}
        </Card>
      </div>
    </>
  );
}
