import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  Award,
  BarChart3,
  CalendarDays,
  ClipboardList,
  Download,
  GitBranch,
  LayoutGrid,
  ReceiptText,
  Sparkles,
  Stethoscope,
  TrendingUp,
  UserRoundCheck,
  Users,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { Link } from "react-router-dom";
import { getList, request } from "../api/client";
import type { Dashboard, ReportDef } from "../api/types";
import { useAuth } from "../auth/context";
import {
  ALL_ROLES,
  BILLING_ROLES,
  CERTIFICATE_READ,
  LEARNER_ROLES,
  MEDICAL_ROLES,
  REPORTING_ROLES,
  can,
} from "../auth/roles";
import type { RoleCode } from "../api/types";
import {
  Card,
  CsvButton,
  EmptyState,
  ErrorState,
  Loading,
  PageHeader,
  Stat,
} from "../components/ui";
import { count, errorMessage, money } from "../lib/format";

interface Dataset {
  key: string;
  label: string;
  description: string;
  icon: LucideIcon;
  roles: RoleCode[];
}

const DATASETS: Dataset[] = [
  {
    key: "learners",
    label: "Learner register",
    description: "Badge, name, company, nationality, position and active status.",
    icon: Users,
    roles: LEARNER_ROLES,
  },
  {
    key: "sessions",
    label: "Session schedule",
    description: "Course, venue, dates, capacity, seats taken and session status.",
    icon: CalendarDays,
    roles: ALL_ROLES,
  },
  {
    key: "enrolments",
    label: "Enrolment trail",
    description: "Booking references, requested and granted sessions, and states.",
    icon: ClipboardList,
    roles: ALL_ROLES,
  },
  {
    key: "certificates",
    label: "Certificate register",
    description: "Certificate numbers, issue and expiry dates, signatures and release.",
    icon: Award,
    roles: CERTIFICATE_READ,
  },
  {
    key: "invoices",
    label: "Invoice ledger",
    description: "Account, learner, dates, totals, payments and invoice status.",
    icon: ReceiptText,
    roles: BILLING_ROLES,
  },
  {
    key: "payments",
    label: "Payment ledger",
    description: "Payment reference, invoice, amount, date, method and status.",
    icon: ReceiptText,
    roles: BILLING_ROLES,
  },
  {
    key: "medicals",
    label: "Medical register",
    description: "Record number, issue and expiry dates, fitness outcome.",
    icon: Stethoscope,
    roles: MEDICAL_ROLES,
  },
  {
    key: "flow",
    label: "Workflow summary",
    description: "Record counts by stage, including terminal and rejected states.",
    icon: Activity,
    roles: REPORTING_ROLES,
  },
];

interface ReportCard {
  dataset: string;
  label: string;
  description: string;
  icon: LucideIcon;
}

const REPORT_CARDS: ReportCard[] = [
  {
    dataset: "training-records",
    label: "Training records",
    description: "Every delegate, course, delivery window and certificate expiry in one ledger.",
    icon: Sparkles,
  },
  {
    dataset: "course-by-month",
    label: "Courses by month",
    description: "Course delivery volume by month, with a year selector for trend review.",
    icon: BarChart3,
  },
  {
    dataset: "learner-by-month",
    label: "Delegates by month",
    description: "Distinct delegates trained each month to track throughput and seasonality.",
    icon: Users,
  },
  {
    dataset: "top-training-courses",
    label: "Top training courses",
    description: "The ten busiest courses for a year, ranked by recorded deliveries.",
    icon: TrendingUp,
  },
  {
    dataset: "courses-treemap",
    label: "Course mix",
    description: "A certificate-type treemap showing where delivery effort is concentrated.",
    icon: LayoutGrid,
  },
  {
    dataset: "role-activity",
    label: "Role activity",
    description: "Completed workflow steps by role, period and person for accountability.",
    icon: UserRoundCheck,
  },
  {
    dataset: "opito-monthly",
    label: "OPITO monthly",
    description: "OPITO course deliveries and learner identifiers for invoice reconciliation.",
    icon: Award,
  },
  {
    dataset: "flow-status",
    label: "Flow status",
    description: "Terminal and active split with backlog and critical workload thresholds.",
    icon: GitBranch,
  },
];

export function ReportsPage() {
  const { user } = useAuth();
  const dashboard = useQuery({
    queryKey: ["dashboard"],
    queryFn: () => request<Dashboard>("/dashboard/"),
  });
  const definitions = useQuery({
    queryKey: ["report-defs"],
    queryFn: () => getList<ReportDef>("/report-defs/", { page_size: 100 }),
    enabled: can(user, REPORTING_ROLES),
  });

  if (!can(user, REPORTING_ROLES)) {
    return (
      <EmptyState
        title="Reporting is restricted"
        body="Your role does not include access to centre-wide reporting."
      />
    );
  }
  if (dashboard.isLoading) return <Loading rows={7} />;
  if (dashboard.isError || !dashboard.data) {
    return (
      <ErrorState
        message={errorMessage(dashboard.error)}
        retry={() => void dashboard.refetch()}
      />
    );
  }

  const data = dashboard.data;
  const available = DATASETS.filter((dataset) => can(user, dataset.roles));

  return (
    <>
      <PageHeader
        eyebrow="Reporting"
        title="Reports & exports"
        description="Role-scoped operational extracts, ready for analysis or handover. Each download is generated from the live database."
      />

      <div className="kpi-grid">
        <Stat
          label="Learners"
          value={count(data.kpis.learners_total)}
          hint={`${count(data.kpis.learners_active)} active`}
          tone="brand"
        />
        <Stat
          label="Certificates"
          value={count(data.kpis.certificates_issued)}
          hint={`${count(data.kpis.certificates_expiring_90d)} expiring in 90 days`}
        />
        <Stat
          label="Collections · 90d"
          value={money(data.kpis.revenue_collected_90d)}
          hint={`${count(data.kpis.invoices_outstanding_count)} invoices open`}
          tone="ok"
        />
        <Stat
          label="Outstanding"
          value={money(data.kpis.invoices_outstanding_total)}
          hint="Issued and part-paid balances"
          tone="warn"
        />
      </div>

      <Card
        title="Reporting intelligence"
        aside={<span className="card-note">Axis parity A· live data</span>}
      >
        <div className="report-grid">
          {REPORT_CARDS.map((report) => {
            const Icon = report.icon;
            return (
              <Link
                className="report-card"
                key={report.dataset}
                to={`/reports/${report.dataset}`}
              >
                <span className="report-icon">
                  <Icon size={19} aria-hidden="true" />
                </span>
                <span className="report-card-body">
                  <strong>{report.label}</strong>
                  <small>{report.description}</small>
                </span>
                <span className="report-open">Open report</span>
              </Link>
            );
          })}
        </div>
      </Card>

      <Card
        title="Operational exports"
        aside={<span className="card-note">CSV A� live data</span>}
      >
        <div className="export-grid">
          {available.map((dataset) => {
            const Icon = dataset.icon;
            return (
              <div className="export-card" key={dataset.key}>
                <span className="export-icon">
                  <Icon size={18} aria-hidden="true" />
                </span>
                <div>
                  <h3>{dataset.label}</h3>
                  <p>{dataset.description}</p>
                </div>
                <CsvButton
                  dataset={dataset.key}
                  label="Download"
                  params={
                    dataset.key === "learners"
                      ? { active: "true" }
                      : undefined
                  }
                />
              </div>
            );
          })}
        </div>
      </Card>

      <div className="dashboard-grid">
        <Card
          title="Workflow distribution"
          aside={<span className="card-note">All training records</span>}
        >
          <div className="flow-bars">
            {data.workflow.map((stage) => {
              const max = Math.max(...data.workflow.map((row) => row.count), 1);
              return (
                <div className="flow-bar-row" key={stage.status}>
                  <span className="flow-name">{stage.name}</span>
                  <span className="flow-meter" aria-hidden="true">
                    <span style={{ width: `${(stage.count / max) * 100}%` }} />
                  </span>
                  <strong>{count(stage.count)}</strong>
                </div>
              );
            })}
          </div>
        </Card>

        <Card
          title="Report catalogue"
          aside={<span className="card-note">{definitions.data?.total ?? 0} definitions</span>}
        >
          {definitions.isLoading ? (
            <Loading rows={4} />
          ) : definitions.isError ? (
            <ErrorState
              message={errorMessage(definitions.error)}
              retry={() => void definitions.refetch()}
            />
          ) : definitions.data?.data.length ? (
            <ul className="plain-list">
              {definitions.data.data.map((definition) => (
                <li key={definition.id}>
                  <span>
                    <strong>{definition.name}</strong>
                    <small className="mono">{definition.code}</small>
                  </span>
                  <Download size={15} aria-hidden="true" />
                </li>
              ))}
            </ul>
          ) : (
            <p className="muted body-copy">
              No report definitions have been seeded. Use the CSV exports for current extracts.
            </p>
          )}
          <p className="hint catalogue-note">
            Definitions describe governed views. The operational exports above are available now.
          </p>
        </Card>
      </div>
    </>
  );
}
