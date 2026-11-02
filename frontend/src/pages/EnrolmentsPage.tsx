import { useState } from "react";
import type { FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BadgeCheck, Plus } from "lucide-react";
import { getList, request } from "../api/client";
import type { CourseSession, Enrolment } from "../api/types";
import { useAuth } from "../auth/context";
import { ENROLMENT_WRITE, can } from "../auth/roles";
import {
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
  StatusBadge,
  Toolbar,
} from "../components/ui";
import { LearnerPicker } from "../components/LearnerPicker";
import { useToast } from "../components/toastContext";
import { errorMessage, formatDate, titleCase } from "../lib/format";
import { useDebounced } from "../lib/hooks";

const STATES = [
  "registered",
  "payment_uploaded",
  "payment_rejected",
  "confirmed",
  "session_transferred",
  "overflow",
  "cancelled",
  "attended",
  "no_show",
  "denied",
];

function BookingEditor({ onClose }: { onClose: () => void }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [learner, setLearner] = useState("");
  const [session, setSession] = useState("");
  const sessions = useQuery({
    queryKey: ["session-options"],
    queryFn: () =>
      getList<CourseSession>("/sessions/", {
        page_size: 150,
        ordering: "start_date",
      }),
  });

  const create = useMutation({
    mutationFn: (payload: { learner: number; requested_session: number }) =>
      request<Enrolment>("/enrolments/", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    onSuccess: (enrolment) => {
      void queryClient.invalidateQueries({ queryKey: ["enrolments"] });
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      void queryClient.invalidateQueries({ queryKey: ["sessions"] });
      toast.push(`Booking ${enrolment.booking_ref ?? ""} created.`);
      onClose();
    },
  });

  const options = (sessions.data?.data ?? []).filter(
    (row) => !["closed", "running"].includes(row.status),
  );

  function submit(event: FormEvent) {
    event.preventDefault();
    create.mutate({ learner: Number(learner), requested_session: Number(session) });
  }

  return (
    <Modal
      open
      onClose={onClose}
      title="Create a booking"
      description="This records a booking request. A seat is only granted after payment verification."
      footer={
        <>
          <Button onClick={onClose}>Cancel</Button>
          <Button type="submit" form="booking-form" variant="primary" busy={create.isPending}>
            Create booking
          </Button>
        </>
      }
    >
      <form id="booking-form" className="form-stack" onSubmit={submit}>
        {create.isError ? (
          <div className="form-error" role="alert">
            {errorMessage(create.error)}
          </div>
        ) : null}
        <Field label="Learner" htmlFor="learner-picker">
          <LearnerPicker id="learner-picker" value={learner} onChange={setLearner} required />
        </Field>
        <Field label="Session" htmlFor="booking-session">
          <Select
            id="booking-session"
            required
            value={session}
            onChange={(event) => setSession(event.target.value)}
          >
            <option value="">{sessions.isLoading ? "Loading sessions…" : "Choose a session"}</option>
            {options.map((row) => (
              <option value={row.id} key={row.id}>
                {row.course_code} · {formatDate(row.start_date)} ·{" "}
                {row.seats_available === null ? "uncapped" : `${row.seats_available} seats`}
              </option>
            ))}
          </Select>
        </Field>
      </form>
    </Modal>
  );
}

export function EnrolmentsPage() {
  const { user } = useAuth();
  const toast = useToast();
  const queryClient = useQueryClient();
  const [query, setQuery] = useState("");
  const [state, setState] = useState("");
  const [page, setPage] = useState(1);
  const [editorOpen, setEditorOpen] = useState(false);
  const [confirming, setConfirming] = useState<Enrolment | null>(null);
  const search = useDebounced(query);

  const enrolments = useQuery({
    queryKey: ["enrolments", search, state, page],
    queryFn: () =>
      getList<Enrolment>("/enrolments/", {
        search,
        state,
        page,
        page_size: 25,
      }),
  });

  const confirm = useMutation({
    mutationFn: (enrolment: Enrolment) =>
      request<Enrolment>(`/enrolments/${enrolment.id}/confirm/`, { method: "POST" }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["enrolments"] });
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      void queryClient.invalidateQueries({ queryKey: ["sessions"] });
      toast.push("Payment verified and seat allocated.");
      setConfirming(null);
    },
  });

  if (enrolments.isLoading) return <Loading rows={7} />;
  if (enrolments.isError || !enrolments.data) {
    return (
      <ErrorState
        message={errorMessage(enrolments.error)}
        retry={() => void enrolments.refetch()}
      />
    );
  }

  const canWrite = can(user, ENROLMENT_WRITE);

  return (
    <>
      <PageHeader
        eyebrow="Bookings"
        title="Enrolments"
        description="Booking requests, payment verification and the granted seat trail."
        actions={
          <>
            <CsvButton dataset="enrolments" label="Export enrolments" />
            {canWrite ? (
              <Button variant="primary" onClick={() => setEditorOpen(true)}>
                <Plus size={16} aria-hidden="true" /> New booking
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
            placeholder="Search booking ref, badge or surname"
          />
          <Select
            aria-label="Filter by booking state"
            value={state}
            onChange={(event) => {
              setState(event.target.value);
              setPage(1);
            }}
          >
            <option value="">All states</option>
            {STATES.map((option) => (
              <option value={option} key={option}>
                {titleCase(option)}
              </option>
            ))}
          </Select>
          <span className="toolbar-count">{enrolments.data.total} bookings</span>
        </Toolbar>

        {enrolments.data.data.length ? (
          <>
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Booking</th>
                    <th>Learner</th>
                    <th>Course</th>
                    <th>Requested start</th>
                    <th>Granted start</th>
                    <th>State</th>
                    {canWrite ? <th aria-label="Actions" /> : null}
                  </tr>
                </thead>
                <tbody>
                  {enrolments.data.data.map((row) => (
                    <tr key={row.id}>
                      <td className="mono">{row.booking_ref ?? `#${row.id}`}</td>
                      <td>
                        <strong>{row.learner_name}</strong>
                        <div className="cell-sub mono">{row.badge_no}</div>
                      </td>
                      <td className="mono">{row.course_code || "—"}</td>
                      <td>{formatDate(row.session_start)}</td>
                      <td>{formatDate(row.granted_start)}</td>
                      <td>
                        <StatusBadge status={row.state} />
                      </td>
                      {canWrite ? (
                        <td className="row-actions">
                          {!["confirmed", "session_transferred", "attended", "cancelled"].includes(
                            row.state,
                          ) ? (
                            <Button size="sm" onClick={() => setConfirming(row)}>
                              <BadgeCheck size={14} aria-hidden="true" /> Verify & seat
                            </Button>
                          ) : null}
                        </td>
                      ) : null}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pagination
              page={enrolments.data.page}
              pageSize={enrolments.data.page_size}
              total={enrolments.data.total}
              onPage={setPage}
            />
          </>
        ) : (
          <EmptyState
            title="No bookings found"
            body={
              query || state
                ? "No booking matches the current search or state."
                : "Book a learner into a scheduled session to begin."
            }
            action={
              canWrite && !query && !state ? (
                <Button variant="primary" onClick={() => setEditorOpen(true)}>
                  Create a booking
                </Button>
              ) : undefined
            }
          />
        )}
      </Card>

      <ConfirmDialog
        open={Boolean(confirming)}
        title="Verify payment and allocate seat"
        message={
          confirming
            ? `Confirm payment for ${confirming.learner_name} (${confirming.badge_no}) on ${confirming.course_code}. The booking will be marked confirmed and a seat granted, with carry-forward applied if the session is full.`
            : ""
        }
        confirmLabel="Verify and confirm"
        busy={confirm.isPending}
        onConfirm={() => {
          if (confirming) confirm.mutate(confirming);
        }}
        onClose={() => setConfirming(null)}
      />
      {confirm.isError ? (
        <div className="form-error floating-error" role="alert">
          {errorMessage(confirm.error)}
        </div>
      ) : null}

      {editorOpen ? <BookingEditor onClose={() => setEditorOpen(false)} /> : null}
    </>
  );
}
