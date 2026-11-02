import { useState } from "react";
import type { FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarPlus, Pencil } from "lucide-react";
import { getList, request } from "../api/client";
import type { CourseSession } from "../api/types";
import { useAuth } from "../auth/context";
import { SCHEDULE_WRITE, can } from "../auth/roles";
import {
  Button,
  Card,
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
  StatusBadge,
  Toolbar,
} from "../components/ui";
import { useToast } from "../components/toastContext";
import { errorMessage, formatDate, titleCase } from "../lib/format";
import { useDebounced } from "../lib/hooks";
import { useReference } from "../lib/useReference";

const SESSION_STATUSES = ["scheduled", "open", "full", "running", "closed"];

function SessionEditor({
  session,
  onClose,
}: {
  session?: CourseSession;
  onClose: () => void;
}) {
  const references = useReference();
  const queryClient = useQueryClient();
  const toast = useToast();
  const [form, setForm] = useState({
    course: session?.course ? String(session.course) : "",
    venue: session?.venue ? String(session.venue) : "",
    start_date: session?.start_date ?? "",
    end_date: session?.end_date ?? "",
    capacity: session?.capacity ? String(session.capacity) : "",
    reserve_pct: session ? String(session.reserve_pct) : "10",
    status: session?.status ?? "scheduled",
  });

  const save = useMutation({
    mutationFn: (payload: Record<string, unknown>) =>
      session
        ? request<CourseSession>(`/sessions/${session.id}/`, {
            method: "PATCH",
            body: JSON.stringify(payload),
          })
        : request<CourseSession>("/sessions/", {
            method: "POST",
            body: JSON.stringify(payload),
          }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["sessions"] });
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      toast.push(session ? "Session updated." : "Session scheduled.");
      onClose();
    },
  });

  function set(key: keyof typeof form, value: string) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    save.mutate({
      course: Number(form.course),
      venue: form.venue ? Number(form.venue) : null,
      start_date: form.start_date,
      end_date: form.end_date || null,
      capacity: form.capacity ? Number(form.capacity) : null,
      reserve_pct: Number(form.reserve_pct || 0),
      status: form.status,
    });
  }

  return (
    <Modal
      open
      onClose={onClose}
      title={session ? "Edit session" : "Schedule a session"}
      description="Capacity is enforced at booking and confirmation, including reserved carry-forward headroom."
      footer={
        <>
          <Button onClick={onClose}>Cancel</Button>
          <Button type="submit" form="session-form" variant="primary" busy={save.isPending}>
            {session ? "Save session" : "Schedule session"}
          </Button>
        </>
      }
    >
      <form id="session-form" className="form-grid" onSubmit={submit}>
        {save.isError ? (
          <div className="form-error form-span" role="alert">
            {errorMessage(save.error)}
          </div>
        ) : null}
        <Field label="Course" htmlFor="session-course" className="form-span">
          <Select
            id="session-course"
            required
            value={form.course}
            onChange={(event) => set("course", event.target.value)}
          >
            <option value="">Choose a course</option>
            {(references.data?.courses ?? [])
              .filter((course) => course.active)
              .map((course) => (
                <option value={course.id} key={course.id}>
                  {course.course_code} · {course.name}
                </option>
              ))}
          </Select>
        </Field>
        <Field label="Venue" htmlFor="session-venue">
          <Select
            id="session-venue"
            value={form.venue}
            onChange={(event) => set("venue", event.target.value)}
          >
            <option value="">Not assigned</option>
            {(references.data?.venues ?? []).map((venue) => (
              <option value={venue.id} key={venue.id}>
                {venue.name}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Seats" htmlFor="session-capacity" hint="Leave blank for uncapped.">
          <Input
            id="session-capacity"
            type="number"
            min="1"
            value={form.capacity}
            onChange={(event) => set("capacity", event.target.value)}
          />
        </Field>
        <Field label="Start date" htmlFor="session-start">
          <Input
            id="session-start"
            type="date"
            required
            value={form.start_date}
            onChange={(event) => set("start_date", event.target.value)}
          />
        </Field>
        <Field label="End date" htmlFor="session-end">
          <Input
            id="session-end"
            type="date"
            value={form.end_date}
            onChange={(event) => set("end_date", event.target.value)}
          />
        </Field>
        <Field label="Reserve headroom %" htmlFor="session-reserve">
          <Input
            id="session-reserve"
            type="number"
            min="0"
            max="100"
            value={form.reserve_pct}
            onChange={(event) => set("reserve_pct", event.target.value)}
          />
        </Field>
        <Field label="Status" htmlFor="session-status">
          <Select
            id="session-status"
            value={form.status}
            onChange={(event) => set("status", event.target.value)}
          >
            {SESSION_STATUSES.map((status) => (
              <option value={status} key={status}>
                {titleCase(status)}
              </option>
            ))}
          </Select>
        </Field>
      </form>
    </Modal>
  );
}

export function SchedulingPage() {
  const { user } = useAuth();
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  const [editor, setEditor] = useState<{ session?: CourseSession } | null>(null);
  const search = useDebounced(query);
  const references = useReference();

  const sessions = useQuery({
    queryKey: ["sessions", search, status, page],
    queryFn: () =>
      getList<CourseSession>("/sessions/", {
        search,
        status,
        page,
        page_size: 25,
      }),
  });

  if (sessions.isLoading) return <Loading rows={7} />;
  if (sessions.isError || !sessions.data) {
    return (
      <ErrorState message={errorMessage(sessions.error)} retry={() => void sessions.refetch()} />
    );
  }

  const canWrite = can(user, SCHEDULE_WRITE);
  const venueName = (id: number | null) =>
    references.data?.venues.find((venue) => venue.id === id)?.name ?? "Unassigned";

  return (
    <>
      <PageHeader
        eyebrow="Delivery calendar"
        title="Scheduling"
        description="Open sessions, seat capacity and the delivery calendar for every course."
        actions={
          <>
            <CsvButton dataset="sessions" label="Export sessions" />
            {canWrite ? (
              <Button variant="primary" onClick={() => setEditor({})}>
                <CalendarPlus size={16} aria-hidden="true" /> New session
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
            placeholder="Search course code or name"
          />
          <Select
            aria-label="Filter by session status"
            value={status}
            onChange={(event) => {
              setStatus(event.target.value);
              setPage(1);
            }}
          >
            <option value="">All statuses</option>
            {SESSION_STATUSES.map((option) => (
              <option value={option} key={option}>
                {titleCase(option)}
              </option>
            ))}
          </Select>
          <span className="toolbar-count">{sessions.data.total} sessions</span>
        </Toolbar>

        {sessions.data.data.length ? (
          <>
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Course</th>
                    <th>Dates</th>
                    <th>Venue</th>
                    <th>Seats</th>
                    <th>Status</th>
                    {canWrite ? <th aria-label="Actions" /> : null}
                  </tr>
                </thead>
                <tbody>
                  {sessions.data.data.map((session) => {
                    const fill = session.capacity
                      ? Math.min(100, Math.round((session.seats_taken / session.capacity) * 100))
                      : 0;
                    const course = references.data?.courses.find(
                      (row) => row.id === session.course,
                    );
                    return (
                      <tr key={session.id}>
                        <td>
                          <strong className="mono">{course?.course_code ?? "Course"}</strong>
                          <div className="cell-sub">{course?.name ?? session.course_name}</div>
                        </td>
                        <td>
                          {formatDate(session.start_date)}
                          <div className="cell-sub">
                            {session.end_date ? `to ${formatDate(session.end_date)}` : "Single day"}
                          </div>
                        </td>
                        <td>{venueName(session.venue)}</td>
                        <td>
                          <div className="seat-cell">
                            <span>
                              {session.seats_taken}
                              {session.capacity ? ` / ${session.capacity}` : " booked"}
                            </span>
                            {session.capacity ? (
                              <span className="seat-bar" aria-hidden="true">
                                <span style={{ width: `${fill}%` }} />
                              </span>
                            ) : null}
                          </div>
                        </td>
                        <td>
                          <StatusBadge status={session.status} />
                        </td>
                        {canWrite ? (
                          <td className="row-actions">
                            <Button size="sm" onClick={() => setEditor({ session })}>
                              <Pencil size={14} aria-hidden="true" /> Edit
                            </Button>
                          </td>
                        ) : null}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <Pagination
              page={sessions.data.page}
              pageSize={sessions.data.page_size}
              total={sessions.data.total}
              onPage={setPage}
            />
          </>
        ) : (
          <EmptyState
            title="No sessions found"
            body={
              query || status
                ? "No session matches this search or status."
                : "Schedule the first course session to start taking bookings."
            }
            action={
              canWrite && !query && !status ? (
                <Button variant="primary" onClick={() => setEditor({})}>
                  Schedule a session
                </Button>
              ) : undefined
            }
          />
        )}
      </Card>

      {editor ? <SessionEditor session={editor.session} onClose={() => setEditor(null)} /> : null}
    </>
  );
}
