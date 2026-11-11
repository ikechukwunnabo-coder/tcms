import { useState } from "react";
import type { ReactNode } from "react";
import { Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  Treemap,
  XAxis,
  YAxis,
} from "recharts";
import { ArrowLeft, Download } from "lucide-react";
import { downloadReport, request } from "../api/client";
import type { ExportFormat } from "../api/client";
import type {
  CourseMonthRow,
  CourseTypeRow,
  DelegateMonthRow,
  FlowStatusReport,
  OpitoMonthlyRow,
  ReportYearRange,
  RoleActivityRow,
  RoleActivitySummaryRow,
  RoleOption,
  TrainingRecordReportRow,
} from "../api/types";
import { useToast } from "../components/toastContext";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorState,
  Field,
  Input,
  Loading,
  PageHeader,
  Stat,
} from "../components/ui";
import { count, errorMessage, formatDate, titleCase } from "../lib/format";

const MONTHS = [
  "Jan",
  "Feb",
  "Mar",
  "Apr",
  "May",
  "Jun",
  "Jul",
  "Aug",
  "Sep",
  "Oct",
  "Nov",
  "Dec",
];

const COLORS = ["#0d7b76", "#c28124", "#476f8c", "#8a5a44", "#6b8f71", "#a45a6b"];

const TOOLTIP_STYLE = {
  background: "#082f35",
  border: "0",
  borderRadius: "10px",
  color: "#f7faf8",
  fontSize: "12px",
};

type ExportParams = Record<string, string | number | boolean | null | undefined>;

function BackLink() {
  return (
    <Link className="btn btn-secondary btn-sm" to="/reports">
      <ArrowLeft size={15} aria-hidden="true" /> All reports
    </Link>
  );
}

function ReportPage({
  title,
  description,
  children,
}: {
  title: string;
  description: string;
  children: ReactNode;
}) {
  return (
    <>
      <PageHeader
        eyebrow="Reporting intelligence"
        title={title}
        description={description}
        actions={<BackLink />}
      />
      {children}
    </>
  );
}

function ExportButtons({
  dataset,
  params,
}: {
  dataset: string;
  params?: ExportParams;
}) {
  const toast = useToast();
  const [busy, setBusy] = useState<ExportFormat | null>(null);

  const run = async (format: ExportFormat) => {
    setBusy(format);
    try {
      await downloadReport(dataset, format, params);
      toast.push(`${format.toUpperCase()} download started.`);
    } catch (error) {
      toast.push(error instanceof Error ? error.message : "Export failed.", "error");
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="export-actions">
      {(["csv", "xlsx", "pdf"] as ExportFormat[]).map((format) => (
        <Button
          key={format}
          size="sm"
          busy={busy === format}
          onClick={() => void run(format)}
        >
          <Download size={14} aria-hidden="true" /> {format.toUpperCase()}
        </Button>
      ))}
    </div>
  );
}

function YearControl({
  range,
  value,
  onChange,
}: {
  range?: ReportYearRange;
  value: number;
  onChange: (year: number) => void;
}) {
  const current = new Date().getFullYear();
  const start = range?.min ?? current;
  const end = range?.max ?? current;
  return (
    <Field label="Delivery year" htmlFor="report-year">
      <select
        id="report-year"
        value={value}
        onChange={(event) => onChange(Number(event.target.value))}
      >
        {Array.from({ length: Math.max(end - start + 1, 1) }, (_, index) => end - index).map(
          (year) => (
            <option key={year} value={year}>
              {year}
            </option>
          ),
        )}
      </select>
    </Field>
  );
}

function useYearRange() {
  return useQuery({
    queryKey: ["report-year-range"],
    queryFn: () => request<ReportYearRange>("/reports/year-range/"),
  });
}

function useYear(defaultYear?: number) {
  const range = useYearRange();
  const current = new Date().getFullYear();
  const [selected, setSelected] = useState<number | null>(null);
  const year = selected ?? defaultYear ?? range.data?.default ?? current;
  return {
    range,
    year,
    setYear: (next: number) => setSelected(next),
  };
}

function TrainingRecordsReport() {
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [search, setSearch] = useState("");
  const query = useQuery({
    queryKey: ["report-training-records", from, to, search],
    queryFn: () =>
      request<{ data: TrainingRecordReportRow[]; total: number }>(
        "/reports/training-records/",
        { params: { from, to, q: search } },
      ),
  });

  if (query.isLoading) return <Loading rows={8} />;
  if (query.isError || !query.data) {
    return <ErrorState message={errorMessage(query.error)} retry={() => void query.refetch()} />;
  }

  const rows = query.data.data;
  const visible = rows.slice(0, 100);

  return (
    <ReportPage
      title="Training records"
      description="A live ledger of delivery, certificate expiry and delegate identity. Filter by window or search by badge and name, then export the full result."
    >
      <Card
        title="Filters"
        aside={<span className="card-note">{count(query.data.total)} records</span>}
      >
        <div className="report-filters">
          <Field label="From" htmlFor="training-from">
            <Input
              id="training-from"
              type="date"
              value={from}
              onChange={(event) => setFrom(event.target.value)}
            />
          </Field>
          <Field label="To" htmlFor="training-to">
            <Input
              id="training-to"
              type="date"
              value={to}
              onChange={(event) => setTo(event.target.value)}
            />
          </Field>
          <Field label="Delegate or badge" htmlFor="training-search">
            <Input
              id="training-search"
              value={search}
              placeholder="Adeyemi or INT001"
              onChange={(event) => setSearch(event.target.value)}
            />
          </Field>
          <div className="report-export-row">
            <ExportButtons
              dataset="training-records"
              params={{ from, to, q: search }}
            />
          </div>
        </div>
      </Card>

      <Card title="Record ledger" aside={<span className="card-note">First 100 shown</span>}>
        {visible.length ? (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th className="num">#</th>
                  <th>Delegate</th>
                  <th>Company</th>
                  <th>Course</th>
                  <th>Start</th>
                  <th>End</th>
                  <th>Expiry</th>
                  <th className="num">Days</th>
                  <th>Certificate</th>
                </tr>
              </thead>
              <tbody>
                {visible.map((row) => (
                  <tr key={row.id}>
                    <td className="num mono">{row.row_num}</td>
                    <td>
                      <strong>{row.first_name} {row.last_name}</strong>
                      <small className="mono">{row.badge_no}</small>
                    </td>
                    <td>{row.company || "-"}</td>
                    <td>{row.course}</td>
                    <td>{formatDate(row.start)}</td>
                    <td>{formatDate(row.end)}</td>
                    <td>{formatDate(row.expiry)}</td>
                    <td className="num">
                      <Badge
                        tone={
                          row.days === ""
                            ? "neutral"
                            : row.days < 0
                              ? "danger"
                              : row.days <= 90
                                ? "warn"
                                : "ok"
                        }
                      >
                        {row.days === "" ? "-" : count(row.days)}
                      </Badge>
                    </td>
                    <td className="mono">{row.certificate || "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState title="No records match" body="Adjust the date window or search term." />
        )}
      </Card>
    </ReportPage>
  );
}

function CourseByMonthReport() {
  const { range, year, setYear } = useYear();
  const query = useQuery({
    queryKey: ["report-course-by-month", year],
    queryFn: () =>
      request<{ year: number; data: CourseMonthRow[] }>("/reports/course-by-month/", {
        params: { year },
      }),
  });

  if (query.isLoading) return <Loading rows={7} />;
  if (query.isError || !query.data) {
    return <ErrorState message={errorMessage(query.error)} retry={() => void query.refetch()} />;
  }

  const rows = query.data.data;
  const totals = MONTHS.map((month) => ({
    month,
    value: rows
      .filter((row) => row.month === month)
      .reduce((sum, row) => sum + row.value, 0),
  }));
  const courses = new Map<number, { code: string; name: string; values: number[] }>();
  for (const row of rows) {
    const course = courses.get(row.c) ?? {
      code: row.course_code,
      name: row.course,
      values: Array(12).fill(0),
    };
    course.values[row.month_no - 1] = row.value;
    courses.set(row.c, course);
  }
  const courseRows = Array.from(courses.entries())
    .map(([id, course]) => ({
      id,
      ...course,
      total: course.values.reduce((sum, value) => sum + value, 0),
    }))
    .sort((a, b) => b.total - a.total);

  return (
    <ReportPage
      title="Courses by month"
      description="Delivery volume by month for the selected year, with the full course matrix below the trend."
    >
      <Card
        title={`${year} delivery trend`}
        aside={<ExportButtons dataset="course-by-month" params={{ year }} />}
      >
        <div className="report-filters">
          <YearControl range={range.data} value={year} onChange={setYear} />
        </div>
        <div className="chart-wrap">
          <ResponsiveContainer width="100%" height={300}>
            <AreaChart data={totals}>
              <defs>
                <linearGradient id="courseMonthFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#0d7b76" stopOpacity={0.28} />
                  <stop offset="100%" stopColor="#0d7b76" stopOpacity={0.02} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 5" stroke="#d9e2df" vertical={false} />
              <XAxis dataKey="month" tickLine={false} axisLine={false} />
              <YAxis allowDecimals={false} tickLine={false} axisLine={false} />
              <Tooltip contentStyle={TOOLTIP_STYLE} />
              <Area
                type="monotone"
                dataKey="value"
                name="Courses delivered"
                stroke="#0d7b76"
                strokeWidth={2.5}
                fill="url(#courseMonthFill)"
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </Card>

      <Card title="Course matrix" aside={<span className="card-note">{courseRows.length} courses</span>}>
        {courseRows.length ? (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Course</th>
                  {MONTHS.map((month) => (
                    <th className="num" key={month}>{month}</th>
                  ))}
                  <th className="num">Total</th>
                </tr>
              </thead>
              <tbody>
                {courseRows.map((course) => (
                  <tr key={course.id}>
                    <td>
                      <strong>{course.name}</strong>
                      <small className="mono">{course.code}</small>
                    </td>
                    {course.values.map((value, index) => (
                      <td className="num" key={MONTHS[index]}>{value || "-"}</td>
                    ))}
                    <td className="num"><strong>{course.total}</strong></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState title="No deliveries in this year" body="Choose another year." />
        )}
      </Card>
    </ReportPage>
  );
}

function DelegatesByMonthReport() {
  const { range, year, setYear } = useYear();
  const query = useQuery({
    queryKey: ["report-delegates-by-month", year],
    queryFn: () =>
      request<{ year: number; data: DelegateMonthRow[] }>(
        "/reports/delegates-by-month/",
        { params: { year } },
      ),
  });

  if (query.isLoading) return <Loading rows={7} />;
  if (query.isError || !query.data) {
    return <ErrorState message={errorMessage(query.error)} retry={() => void query.refetch()} />;
  }

  const rows = query.data.data;
  const total = rows.reduce((sum, row) => sum + row.value, 0);
  const peak = rows.reduce((best, row) => (row.value > best.value ? row : best), rows[0]);

  return (
    <ReportPage
      title="Delegates by month"
      description="Distinct delegates trained each month, useful for capacity planning and monthly performance conversations."
    >
      <div className="kpi-grid">
        <Stat label="Monthly delegate records" value={count(total)} tone="brand" />
        <Stat label="Peak month" value={peak?.month ?? "-"} hint={`${peak?.value ?? 0} delegates`} tone="ok" />
        <Stat label="Year" value={year} hint="Selected delivery year" />
      </div>
      <Card
        title={`${year} delegate flow`}
        aside={<ExportButtons dataset="delegates-by-month" params={{ year }} />}
      >
        <div className="report-filters">
          <YearControl range={range.data} value={year} onChange={setYear} />
        </div>
        <div className="chart-wrap">
          <ResponsiveContainer width="100%" height={310}>
            <BarChart data={rows}>
              <CartesianGrid strokeDasharray="3 5" stroke="#d9e2df" vertical={false} />
              <XAxis dataKey="month" tickLine={false} axisLine={false} />
              <YAxis allowDecimals={false} tickLine={false} axisLine={false} />
              <Tooltip contentStyle={TOOLTIP_STYLE} />
              <Bar dataKey="value" name="Delegates" fill="#c28124" radius={[5, 5, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </Card>
    </ReportPage>
  );
}

function TopCoursesReport() {
  const { range, year, setYear } = useYear();
  const query = useQuery({
    queryKey: ["report-top-courses", year],
    queryFn: () =>
      request<{ year: number; data: CourseMonthRow[] }>("/reports/top-courses/", {
        params: { year },
      }),
  });

  if (query.isLoading) return <Loading rows={7} />;
  if (query.isError || !query.data) {
    return <ErrorState message={errorMessage(query.error)} retry={() => void query.refetch()} />;
  }

  const totals = new Map<number, { course: string; code: string; total: number }>();
  for (const row of query.data.data) {
    const current = totals.get(row.c) ?? { course: row.course, code: row.course_code, total: 0 };
    current.total += row.value;
    totals.set(row.c, current);
  }
  const rows = Array.from(totals.values()).sort((a, b) => b.total - a.total);

  return (
    <ReportPage
      title="Top training courses"
      description="The ten busiest courses for the selected year, ranked by recorded course deliveries."
    >
      <Card
        title={`${year} course ranking`}
        aside={<ExportButtons dataset="top-courses" params={{ year }} />}
      >
        <div className="report-filters">
          <YearControl range={range.data} value={year} onChange={setYear} />
        </div>
        {rows.length ? (
          <div className="chart-wrap">
            <ResponsiveContainer width="100%" height={Math.max(rows.length * 38, 260)}>
              <BarChart data={rows} layout="vertical" margin={{ left: 20, right: 18 }}>
                <CartesianGrid strokeDasharray="3 5" stroke="#d9e2df" horizontal={false} />
                <XAxis type="number" allowDecimals={false} tickLine={false} axisLine={false} />
                <YAxis
                  dataKey="course"
                  type="category"
                  width={170}
                  tickLine={false}
                  axisLine={false}
                />
                <Tooltip contentStyle={TOOLTIP_STYLE} />
                <Bar dataKey="total" name="Deliveries" fill="#0d7b76" radius={[0, 5, 5, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        ) : (
          <EmptyState title="No courses in this year" body="Choose another year." />
        )}
        {rows.length ? (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Course</th>
                  <th>Code</th>
                  <th className="num">Deliveries</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.code}>
                    <td>{row.course}</td>
                    <td className="mono">{row.code}</td>
                    <td className="num"><strong>{row.total}</strong></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </Card>
    </ReportPage>
  );
}

function CourseMixReport() {
  const { range, year, setYear } = useYear();
  const query = useQuery({
    queryKey: ["report-courses-treemap", year],
    queryFn: () =>
      request<{ year: number; data: CourseTypeRow[] }>("/reports/courses-treemap/", {
        params: { year },
      }),
  });

  if (query.isLoading) return <Loading rows={7} />;
  if (query.isError || !query.data) {
    return <ErrorState message={errorMessage(query.error)} retry={() => void query.refetch()} />;
  }

  const rows = query.data.data;
  const types = Array.from(new Set(rows.map((row) => row.type)));
  const hierarchy = types.map((type, index) => ({
    name: type,
    fill: COLORS[index % COLORS.length],
    children: rows
      .filter((row) => row.type === type)
      .map((row) => ({ name: row.course, size: row.count, fill: COLORS[index % COLORS.length] })),
  }));
  const typeTotals = types.map((type) => ({
    type,
    count: rows.filter((row) => row.type === type).reduce((sum, row) => sum + row.count, 0),
    courses: rows.filter((row) => row.type === type).length,
  }));

  return (
    <ReportPage
      title="Course mix"
      description="Certificate-type composition for the selected year. Larger blocks show where delivery volume is concentrated."
    >
      <Card
        title={`${year} course composition`}
        aside={<ExportButtons dataset="courses-treemap" params={{ year }} />}
      >
        <div className="report-filters">
          <YearControl range={range.data} value={year} onChange={setYear} />
        </div>
        {hierarchy.length ? (
          <div className="chart-wrap">
            <ResponsiveContainer width="100%" height={360}>
              <Treemap
                data={hierarchy}
                dataKey="size"
                nameKey="name"
                aspectRatio={4 / 3}
                stroke="#f7faf8"
              />
            </ResponsiveContainer>
          </div>
        ) : (
          <EmptyState title="No course mix in this year" body="Choose another year." />
        )}
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Certificate type</th>
                <th className="num">Courses</th>
                <th className="num">Deliveries</th>
              </tr>
            </thead>
            <tbody>
              {typeTotals.map((row) => (
                <tr key={row.type}>
                  <td>{row.type}</td>
                  <td className="num">{row.courses}</td>
                  <td className="num"><strong>{row.count}</strong></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </ReportPage>
  );
}

function RoleActivityReport() {
  const roles = useQuery({
    queryKey: ["report-role-activity-roles"],
    queryFn: () => request<{ data: RoleOption[] }>("/reports/role-activity/roles/"),
  });
  const earliest = useQuery({
    queryKey: ["report-role-activity-earliest"],
    queryFn: () => request<{ date: string | null }>("/reports/role-activity/earliest-date/"),
  });
  const [role, setRole] = useState("");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const params = { role, from, to };
  const activity = useQuery({
    queryKey: ["report-role-activity", role, from, to],
    queryFn: () =>
      request<{ data: RoleActivityRow[]; total: number }>("/reports/role-activity/", {
        params,
      }),
  });
  const summary = useQuery({
    queryKey: ["report-role-activity-summary", role, from, to],
    queryFn: () =>
      request<{ data: RoleActivitySummaryRow[]; total: number }>(
        "/reports/role-activity/summary/",
        { params },
      ),
  });

  const loading = activity.isLoading || summary.isLoading;
  if (loading) return <Loading rows={7} />;
  if (activity.isError || summary.isError || !activity.data || !summary.data) {
    return (
      <ErrorState
        message={errorMessage(activity.error ?? summary.error)}
        retry={() => {
          void activity.refetch();
          void summary.refetch();
        }}
      />
    );
  }

  return (
    <ReportPage
      title="Role activity"
      description="Every completed workflow action, attributed to the acting person and role. Use the summary to compare workload across the team."
    >
      <Card
        title="Period and role"
        aside={<ExportButtons dataset="role-activity" params={params} />}
      >
        <div className="report-filters">
          <Field label="Role" htmlFor="activity-role">
            <select
              id="activity-role"
              value={role}
              onChange={(event) => setRole(event.target.value)}
            >
              <option value="">All roles</option>
              {roles.data?.data.map((option) => (
                <option key={option.id} value={option.id}>{option.name}</option>
              ))}
            </select>
          </Field>
          <Field
            label="From"
            htmlFor="activity-from"
            hint={earliest.data?.date ? `Activity starts ${earliest.data.date}` : undefined}
          >
            <Input
              id="activity-from"
              type="date"
              value={from}
              onChange={(event) => setFrom(event.target.value)}
            />
          </Field>
          <Field label="To" htmlFor="activity-to">
            <Input
              id="activity-to"
              type="date"
              value={to}
              onChange={(event) => setTo(event.target.value)}
            />
          </Field>
        </div>
      </Card>

      <div className="kpi-grid">
        <Stat label="Completed steps" value={count(activity.data.total)} tone="brand" />
        <Stat label="Contributors" value={count(summary.data.total)} tone="ok" />
        <Stat
          label="Top contributor"
          value={summary.data.data[0]?.name ?? "-"}
          hint={summary.data.data[0] ? `${summary.data.data[0].count} steps` : undefined}
        />
      </div>

      <div className="dashboard-grid">
        <Card title="Completed actions" aside={<span className="card-note">Latest first</span>}>
          {activity.data.data.length ? (
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Person</th>
                    <th>Delegate</th>
                    <th>Course</th>
                    <th>Step</th>
                    <th>Action</th>
                    <th>Completed</th>
                  </tr>
                </thead>
                <tbody>
                  {activity.data.data.slice(0, 100).map((row) => (
                    <tr key={row.id}>
                      <td>{row.user || "-"}</td>
                      <td>
                        <strong>{row.learner}</strong>
                        <small className="mono">{row.badge_no}</small>
                      </td>
                      <td>{row.course}</td>
                      <td>{row.step}</td>
                      <td><Badge tone={row.action === "approve" ? "ok" : "warn"}>{titleCase(row.action)}</Badge></td>
                      <td>{formatDate(row.completed)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <EmptyState title="No completed actions" body="Try another role or widen the period." />
          )}
        </Card>

        <Card title="User summary" aside={<span className="card-note">Step count</span>}>
          {summary.data.data.length ? (
            <ul className="plain-list">
              {summary.data.data.map((row) => (
                <li key={row.username}>
                  <span>
                    <strong>{row.name}</strong>
                    <small className="mono">{row.username}</small>
                  </span>
                  <strong>{row.count}</strong>
                </li>
              ))}
            </ul>
          ) : (
            <p className="muted body-copy">No actions in this period.</p>
          )}
        </Card>
      </div>
    </ReportPage>
  );
}

function OpitoMonthlyReport() {
  const current = new Date();
  const start = `${current.getFullYear()}-01-01`;
  const end = current.toISOString().slice(0, 10);
  const [from, setFrom] = useState(start);
  const [to, setTo] = useState(end);
  const query = useQuery({
    queryKey: ["report-opito-monthly", from, to],
    queryFn: () =>
      request<{ data: OpitoMonthlyRow[]; total: number }>("/reports/opito-monthly/", {
        params: { from, to },
      }),
  });

  if (query.isLoading) return <Loading rows={7} />;
  if (query.isError || !query.data) {
    return <ErrorState message={errorMessage(query.error)} retry={() => void query.refetch()} />;
  }

  const rows = query.data.data;
  const byCourse = new Map<string, { course: string; code: string; total: number }>();
  for (const row of rows) {
    const current = byCourse.get(row.course_code) ?? {
      course: row.course,
      code: row.course_code,
      total: 0,
    };
    current.total += 1;
    byCourse.set(row.course_code, current);
  }
  const chart = Array.from(byCourse.values()).sort((a, b) => b.total - a.total);

  return (
    <ReportPage
      title="OPITO monthly"
      description="OPITO course deliveries with learner identifiers, ready for monthly invoice reconciliation."
    >
      <Card
        title="Reconciliation window"
        aside={<ExportButtons dataset="opito-monthly" params={{ from, to }} />}
      >
        <div className="report-filters">
          <Field label="From" htmlFor="opito-from">
            <Input
              id="opito-from"
              type="date"
              value={from}
              onChange={(event) => setFrom(event.target.value)}
            />
          </Field>
          <Field label="To" htmlFor="opito-to">
            <Input
              id="opito-to"
              type="date"
              value={to}
              onChange={(event) => setTo(event.target.value)}
            />
          </Field>
        </div>
      </Card>

      <div className="kpi-grid">
        <Stat label="OPITO records" value={count(rows.length)} tone="brand" />
        <Stat label="Courses" value={count(chart.length)} tone="ok" />
        <Stat
          label="Unique delegates"
          value={count(new Set(rows.map((row) => row.badge_no)).size)}
        />
      </div>

      <div className="dashboard-grid">
        <Card title="Deliveries by course">
          {chart.length ? (
            <div className="chart-wrap">
              <ResponsiveContainer width="100%" height={Math.max(chart.length * 36, 240)}>
                <BarChart data={chart} layout="vertical" margin={{ left: 20, right: 18 }}>
                  <CartesianGrid strokeDasharray="3 5" stroke="#d9e2df" horizontal={false} />
                  <XAxis type="number" allowDecimals={false} tickLine={false} axisLine={false} />
                  <YAxis dataKey="course" type="category" width={170} tickLine={false} axisLine={false} />
                  <Tooltip contentStyle={TOOLTIP_STYLE} />
                  <Bar dataKey="total" name="Records" fill="#0d7b76" radius={[0, 5, 5, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <EmptyState title="No OPITO records" body="Widen the reconciliation window." />
          )}
        </Card>

        <Card title="Learner identifiers" aside={<span className="card-note">Latest records</span>}>
          {rows.length ? (
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Delegate</th>
                    <th>OPITO ID</th>
                    <th>Course</th>
                    <th>Start</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.slice(0, 50).map((row) => (
                    <tr key={row.id}>
                      <td>
                        <strong>{row.learner}</strong>
                        <small className="mono">{row.badge_no}</small>
                      </td>
                      <td className="mono">{row.opito_learner_id || "-"}</td>
                      <td>{row.course}</td>
                      <td>{formatDate(row.start)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="muted body-copy">No identifiers in this window.</p>
          )}
        </Card>
      </div>
    </ReportPage>
  );
}

function FlowStatusReport() {
  const query = useQuery({
    queryKey: ["report-flow-status"],
    queryFn: () => request<FlowStatusReport>("/reports/flow-status/"),
  });

  if (query.isLoading) return <Loading rows={7} />;
  if (query.isError || !query.data) {
    return <ErrorState message={errorMessage(query.error)} retry={() => void query.refetch()} />;
  }

  const data = query.data;
  const rows = data.data.filter((row) => row.count > 0 || !row.terminal);
  const levelColor = (level: string) => {
    if (level === "critical") return "#a63d40";
    if (level === "backlog") return "#c28124";
    if (level === "terminal") return "#6b8f71";
    return "#0d7b76";
  };

  return (
    <ReportPage
      title="Flow status"
      description="Terminal versus active workload, with backlog and critical thresholds applied to each workflow stage."
    >
      <div className="kpi-grid">
        <Stat label="Active records" value={count(data.summary.active_records)} tone="brand" />
        <Stat label="Terminal records" value={count(data.summary.terminal_records)} tone="ok" />
        <Stat
          label="Backlog records"
          value={count(data.summary.backlog_records)}
          hint={`${data.thresholds.backlog}+ per stage`}
          tone="warn"
        />
        <Stat
          label="Critical records"
          value={count(data.summary.critical_records)}
          hint={`${data.thresholds.critical}+ per stage`}
          tone="danger"
        />
      </div>

      <div className="dashboard-grid">
        <Card
          title="Workload by stage"
          aside={<ExportButtons dataset="flow" />}
        >
          {rows.length ? (
            <div className="chart-wrap">
              <ResponsiveContainer width="100%" height={Math.max(rows.length * 34, 300)}>
                <BarChart data={rows} layout="vertical" margin={{ left: 20, right: 18 }}>
                  <CartesianGrid strokeDasharray="3 5" stroke="#d9e2df" horizontal={false} />
                  <XAxis type="number" allowDecimals={false} tickLine={false} axisLine={false} />
                  <YAxis dataKey="name" type="category" width={160} tickLine={false} axisLine={false} />
                  <Tooltip contentStyle={TOOLTIP_STYLE} />
                  <Bar dataKey="count" name="Records" radius={[0, 5, 5, 0]}>
                    {rows.map((row) => (
                      <Cell key={row.id} fill={levelColor(row.level)} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <EmptyState title="No workflow records" body="The flow is currently empty." />
          )}
        </Card>

        <Card title="Threshold watch" aside={<span className="card-note">Active stages</span>}>
          <ul className="plain-list">
            {rows
              .filter((row) => !row.terminal && (row.level !== "normal" || row.next_role))
              .map((row) => (
                <li key={row.id}>
                  <span>
                    <strong>{row.name}</strong>
                    <small>{row.next_role_name || "No next role"}</small>
                  </span>
                  <Badge tone={row.level === "critical" ? "danger" : row.level === "backlog" ? "warn" : "neutral"}>
                    {row.count}
                  </Badge>
                </li>
              ))}
          </ul>
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Next role</th>
                  <th className="num">Open</th>
                  <th>Stages</th>
                </tr>
              </thead>
              <tbody>
                {data.next_roles.map((role) => (
                  <tr key={role.role}>
                    <td>{role.name}</td>
                    <td className="num"><strong>{role.count}</strong></td>
                    <td><small>{role.stages.join(", ")}</small></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      </div>
    </ReportPage>
  );
}

const REPORT_META: Record<string, { title: string; description: string }> = {
  "training-records": {
    title: "Training records",
    description: "Live delivery ledger",
  },
  "course-by-month": {
    title: "Courses by month",
    description: "Delivery trend",
  },
  "learner-by-month": {
    title: "Delegates by month",
    description: "Monthly throughput",
  },
  "top-training-courses": {
    title: "Top training courses",
    description: "Course ranking",
  },
  "courses-treemap": {
    title: "Course mix",
    description: "Certificate composition",
  },
  "role-activity": {
    title: "Role activity",
    description: "Workflow accountability",
  },
  "opito-monthly": {
    title: "OPITO monthly",
    description: "Invoice reconciliation",
  },
  "flow-status": {
    title: "Flow status",
    description: "Workload thresholds",
  },
};

export function ReportDetailPage() {
  const { dataset = "" } = useParams();
  if (!REPORT_META[dataset]) {
    return (
      <EmptyState
        title="Report not found"
        body="This report does not exist. Return to the reporting index to choose another view."
      />
    );
  }

  return (
    <div className="report-detail">
      {dataset === "training-records" ? <TrainingRecordsReport /> : null}
      {dataset === "course-by-month" ? <CourseByMonthReport /> : null}
      {dataset === "learner-by-month" ? <DelegatesByMonthReport /> : null}
      {dataset === "top-training-courses" ? <TopCoursesReport /> : null}
      {dataset === "courses-treemap" ? <CourseMixReport /> : null}
      {dataset === "role-activity" ? <RoleActivityReport /> : null}
      {dataset === "opito-monthly" ? <OpitoMonthlyReport /> : null}
      {dataset === "flow-status" ? <FlowStatusReport /> : null}
    </div>
  );
}
