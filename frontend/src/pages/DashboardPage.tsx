import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import {
  Area,
  AreaChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { ArrowUpRight, RefreshCw } from "lucide-react";
import { request } from "../api/client";
import type { Dashboard } from "../api/types";
import { useAuth } from "../auth/context";
import { REPORTING_ROLES, can } from "../auth/roles";
import {
  Button,
  Card,
  CsvButton,
  ErrorState,
  Loading,
  PageHeader,
  Stat,
  StatusBadge,
} from "../components/ui";
import { count, errorMessage, formatDate, money, titleCase } from "../lib/format";

function monthLabel(value: string) {
  const [year, month] = value.split("-").map(Number);
  return new Intl.DateTimeFormat("en-GB", { month: "short" }).format(
    new Date(year, month - 1, 1),
  );
}

export function DashboardPage() {
  const { user } = useAuth();
  const dashboard = useQuery({
    queryKey: ["dashboard"],
    queryFn: () => request<Dashboard>("/dashboard/"),
    refetchInterval: 60_000,
  });

  if (dashboard.isLoading) return <Loading rows={8} />;
  if (dashboard.isError || !dashboard.data) {
    return (
      <ErrorState
        message={errorMessage(dashboard.error)}
        retry={() => void dashboard.refetch()}
      />
    );
  }

  const data = dashboard.data;
  const trend = data.trend.map((row) => ({ ...row, label: monthLabel(row.month) }));
  const queueTotal =
    data.work_queue.pending_enrolments.length +
    data.work_queue.unpaid_invoices.length +
    data.work_queue.certificates_awaiting_release.length;

  return (
    <>
      <PageHeader
        eyebrow="Operations board"
        title="Today at the centre"
        description="A live read on throughput, cash, certification and the work waiting on a decision."
        actions={
          <>
            <Button onClick={() => void dashboard.refetch()}>
              <RefreshCw size={16} aria-hidden="true" /> Refresh
            </Button>
            {can(user, REPORTING_ROLES) ? <CsvButton dataset="flow" label="Export flow" /> : null}
          </>
        }
      />

      <div className="kpi-grid">
        <Stat
          label="Active learners"
          value={count(data.kpis.learners_active)}
          hint={`${count(data.kpis.learners_total)} on the register`}
          tone="brand"
        />
        <Stat
          label="Upcoming sessions"
          value={count(data.kpis.sessions_upcoming)}
          hint="Scheduled or open"
        />
        <Stat
          label="Pending enrolments"
          value={count(data.kpis.enrolments_pending)}
          hint="Awaiting payment or verification"
          tone={data.kpis.enrolments_pending ? "warn" : "neutral"}
        />
        <Stat
          label="Collected · 90 days"
          value={money(data.kpis.revenue_collected_90d)}
          hint={`${count(data.kpis.invoices_outstanding_count)} invoices outstanding`}
          tone="ok"
        />
      </div>

      <div className="mini-grid">
        <div className="mini-stat">
          <span>Certificates issued</span>
          <strong>{count(data.kpis.certificates_issued)}</strong>
        </div>
        <div className="mini-stat">
          <span>Expiring in 90 days</span>
          <strong>{count(data.kpis.certificates_expiring_90d)}</strong>
        </div>
        <div className="mini-stat">
          <span>Outstanding value</span>
          <strong>{money(data.kpis.invoices_outstanding_total)}</strong>
        </div>
        <div className="mini-stat">
          <span>Medicals expiring · 30d</span>
          <strong>{count(data.kpis.medicals_expiring_30d)}</strong>
        </div>
        <div className="mini-stat">
          <span>Open workflow records</span>
          <strong>{count(data.kpis.workflow_open)}</strong>
        </div>
      </div>

      <div className="dashboard-grid">
        <Card
          title="Six-month throughput"
          aside={<span className="card-note">Bookings and certificates issued</span>}
          className="chart-card"
        >
          <div className="chart-wrap">
            <ResponsiveContainer width="100%" height={280}>
              <AreaChart data={trend} margin={{ top: 12, right: 8, left: -18, bottom: 0 }}>
                <defs>
                  <linearGradient id="enrolmentFill" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#0d7b76" stopOpacity={0.28} />
                    <stop offset="100%" stopColor="#0d7b76" stopOpacity={0.02} />
                  </linearGradient>
                  <linearGradient id="certificateFill" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#c28124" stopOpacity={0.24} />
                    <stop offset="100%" stopColor="#c28124" stopOpacity={0.02} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 5" stroke="#d9e2df" vertical={false} />
                <XAxis
                  dataKey="label"
                  tickLine={false}
                  axisLine={false}
                  tick={{ fill: "#5f6f6b", fontSize: 12 }}
                />
                <YAxis
                  allowDecimals={false}
                  tickLine={false}
                  axisLine={false}
                  tick={{ fill: "#5f6f6b", fontSize: 12 }}
                />
                <Tooltip
                  contentStyle={{
                    background: "#082f35",
                    border: "0",
                    borderRadius: "10px",
                    color: "#f7faf8",
                    fontSize: "12px",
                  }}
                />
                <Legend iconType="circle" wrapperStyle={{ fontSize: "12px" }} />
                <Area
                  type="monotone"
                  dataKey="enrolments"
                  name="Enrolments"
                  stroke="#0d7b76"
                  strokeWidth={2.5}
                  fill="url(#enrolmentFill)"
                />
                <Area
                  type="monotone"
                  dataKey="certificates"
                  name="Certificates"
                  stroke="#c28124"
                  strokeWidth={2.5}
                  fill="url(#certificateFill)"
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </Card>

        <Card
          title="Your approval stages"
          aside={
            <Link className="text-link" to="/workflow">
              Open workflow <ArrowUpRight size={14} aria-hidden="true" />
            </Link>
          }
        >
          {data.my_stages.length ? (
            <div className="stage-list">
              {data.my_stages.map((stage) => (
                <Link
                  key={stage.status}
                  to={`/workflow?status=${stage.status}`}
                  className="stage-row"
                >
                  <span className="stage-index">{String(stage.status).padStart(2, "0")}</span>
                  <span className="stage-name">
                    <strong>{stage.name}</strong>
                    <small>{titleCase(stage.code)}</small>
                  </span>
                  <span className={`stage-count ${stage.count ? "has-work" : ""}`}>
                    {count(stage.count)}
                  </span>
                </Link>
              ))}
            </div>
          ) : (
            <p className="muted body-copy">
              No approval stages are assigned to your role. You can still follow the centre-wide
              workflow.
            </p>
          )}
        </Card>
      </div>

      <div className="dashboard-grid">
        <Card
          title="Next sessions"
          aside={
            <Link className="text-link" to="/scheduling">
              Full schedule <ArrowUpRight size={14} aria-hidden="true" />
            </Link>
          }
        >
          {data.upcoming_sessions.length ? (
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Course</th>
                    <th>Start</th>
                    <th>Venue</th>
                    <th className="num">Fill</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {data.upcoming_sessions.map((session) => (
                    <tr key={session.id}>
                      <td>
                        <strong className="mono">{session.course_code}</strong>
                        <div className="cell-sub">{session.course_name}</div>
                      </td>
                      <td>{formatDate(session.start_date)}</td>
                      <td>{session.venue || "—"}</td>
                      <td className="num">
                        {session.seats_taken}
                        {session.capacity ? ` / ${session.capacity}` : ""}
                      </td>
                      <td>
                        <StatusBadge status={session.status} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="muted body-copy">No upcoming sessions are currently scheduled.</p>
          )}
        </Card>

        <Card
          title="Action queue"
          aside={<span className="card-note">{count(queueTotal)} open items</span>}
        >
          <div className="queue">
            <div className="queue-head">
              <span>Enrolments to verify</span>
              <Link to="/enrolments?state=registered">View all</Link>
            </div>
            {data.work_queue.pending_enrolments.slice(0, 3).map((row) => (
              <Link to={`/enrolments?q=${row.booking_ref ?? ""}`} key={row.id} className="queue-row">
                <span>
                  <strong>{row.learner}</strong>
                  <small>
                    {row.badge_no} · {row.course_code}
                  </small>
                </span>
                <StatusBadge status={row.state} />
              </Link>
            ))}
            {!data.work_queue.pending_enrolments.length ? (
              <p className="queue-empty">Nothing waiting.</p>
            ) : null}

            <div className="queue-head">
              <span>Invoices outstanding</span>
              <Link to="/billing?tab=invoices">View billing</Link>
            </div>
            {data.work_queue.unpaid_invoices.slice(0, 3).map((row) => (
              <Link to={`/billing?tab=invoices&q=${row.invoice_no}`} key={row.id} className="queue-row">
                <span>
                  <strong className="mono">{row.invoice_no}</strong>
                  <small>Due {formatDate(row.due_date)}</small>
                </span>
                <span className="queue-amount">{money(row.balance, row.currency)}</span>
              </Link>
            ))}
            {!data.work_queue.unpaid_invoices.length ? (
              <p className="queue-empty">Nothing outstanding.</p>
            ) : null}

            <div className="queue-head">
              <span>Certificates waiting release</span>
              <Link to="/certificates">View certificates</Link>
            </div>
            {data.work_queue.certificates_awaiting_release.slice(0, 3).map((row) => (
              <Link to={`/certificates?q=${row.certificate_no}`} key={row.id} className="queue-row">
                <span>
                  <strong>{row.learner}</strong>
                  <small className="mono">{row.certificate_no}</small>
                </span>
                <span className={`mini-flag ${row.md_approved ? "ok" : "warn"}`}>
                  {row.md_approved ? "Signed" : "Needs MD"}
                </span>
              </Link>
            ))}
            {!data.work_queue.certificates_awaiting_release.length ? (
              <p className="queue-empty">Nothing waiting.</p>
            ) : null}
          </div>
        </Card>
      </div>
    </>
  );
}
