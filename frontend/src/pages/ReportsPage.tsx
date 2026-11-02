import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  Award,
  CalendarDays,
  ClipboardList,
  Download,
  ReceiptText,
  Stethoscope,
  Users,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
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
        title="Operational exports"
        aside={<span className="card-note">CSV · live data</span>}
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
