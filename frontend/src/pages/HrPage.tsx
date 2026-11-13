import { Fragment, useState } from "react";
import type { FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import {
  Check,
  Pencil,
  Plus,
  Send,
  X,
} from "lucide-react";
import { getList, request } from "../api/client";
import type {
  Employee,
  EmployeePayElement,
  PayElement,
  Payslip,
  Position,
  Provision,
  TimeEntry,
  Timesheet,
} from "../api/types";
import { useAuth } from "../auth/context";
import { HR_MANAGER_ROLES, can, isHrOnly } from "../auth/roles";
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
import {
  errorMessage,
  formatDate,
  money,
  titleCase,
} from "../lib/format";
import { useDebounced } from "../lib/hooks";

type Tab =
  | "employees"
  | "positions"
  | "timesheets"
  | "payslips"
  | "pay-setup"
  | "provisions";

const BASE_TABS: { id: Tab; label: string }[] = [
  { id: "employees", label: "Employees" },
  { id: "positions", label: "Positions" },
  { id: "timesheets", label: "Time & attendance" },
];

const MANAGER_TABS: { id: Tab; label: string }[] = [
  { id: "payslips", label: "Payslips" },
  { id: "pay-setup", label: "Pay setup" },
  { id: "provisions", label: "Provisions" },
];

function todayISO() {
  const now = new Date();
  return new Date(now.getTime() - now.getTimezoneOffset() * 60_000)
    .toISOString()
    .slice(0, 10);
}

function firstError(error: unknown) {
  return errorMessage(error);
}

function EmployeeEditor({
  employee,
  positions,
  sensitive,
  onClose,
}: {
  employee?: Employee;
  positions: Position[];
  sensitive: boolean;
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [form, setForm] = useState({
    staff_no: employee?.staff_no ?? "",
    full_name: employee?.full_name ?? "",
    position: employee?.position ? String(employee.position) : "",
    pay_frequency: employee?.pay_frequency ?? "monthly",
    basic_salary: employee?.basic_salary ?? "",
    hourly_rate: employee?.hourly_rate ?? "",
    bank_name: employee?.bank_name ?? "",
    bank_code: employee?.bank_code ?? "",
    account_name: employee?.account_name ?? "",
    bank_account: employee?.bank_account ?? "",
    tax_id: employee?.tax_id ?? "",
    pension_id: employee?.pension_id ?? "",
    active: employee?.active ?? true,
  });

  const save = useMutation({
    mutationFn: () => {
      const payload: Record<string, unknown> = {
        staff_no: form.staff_no.trim(),
        full_name: form.full_name.trim(),
        position: form.position ? Number(form.position) : null,
        pay_frequency: form.pay_frequency,
        tax_id: form.tax_id.trim(),
        pension_id: form.pension_id.trim(),
        active: form.active,
      };
      if (sensitive) {
        payload.basic_salary = form.basic_salary || null;
        payload.hourly_rate = form.hourly_rate || null;
        payload.bank_name = form.bank_name;
        payload.bank_code = form.bank_code;
        payload.account_name = form.account_name;
        payload.bank_account = form.bank_account;
      }
      return employee
        ? request<Employee>(`/payroll-employees/${employee.id}/`, {
            method: "PATCH",
            body: JSON.stringify(payload),
          })
        : request<Employee>("/payroll-employees/", {
            method: "POST",
            body: JSON.stringify(payload),
          });
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["hr-employees"] });
      toast.push(employee ? "Employee updated." : "Employee created.");
      onClose();
    },
  });

  function set(key: keyof typeof form, value: string | boolean) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  return (
    <Modal
      open
      wide
      onClose={onClose}
      title={employee ? "Edit employee" : "New employee"}
      description={
        sensitive
          ? "Pay and bank details are restricted to HR Managers and finance roles."
          : "Salary, bank details and payslips are hidden from your HR Officer view."
      }
      footer={
        <>
          <Button onClick={onClose}>Cancel</Button>
          <Button
            type="submit"
            form="employee-form"
            variant="primary"
            busy={save.isPending}
          >
            {employee ? "Save changes" : "Create employee"}
          </Button>
        </>
      }
    >
      <form
        id="employee-form"
        className="form-grid"
        onSubmit={(event: FormEvent) => {
          event.preventDefault();
          save.mutate();
        }}
      >
        {save.isError ? (
          <div className="form-error form-span" role="alert">
            {firstError(save.error)}
          </div>
        ) : null}
        <Field label="Staff number" htmlFor="employee-staff-no">
          <Input
            id="employee-staff-no"
            value={form.staff_no}
            onChange={(event) => set("staff_no", event.target.value)}
            required
          />
        </Field>
        <Field label="Full name" htmlFor="employee-name">
          <Input
            id="employee-name"
            value={form.full_name}
            onChange={(event) => set("full_name", event.target.value)}
            required
          />
        </Field>
        <Field label="Position" htmlFor="employee-position">
          <Select
            id="employee-position"
            value={form.position}
            onChange={(event) => set("position", event.target.value)}
          >
            <option value="">No position</option>
            {positions.map((position) => (
              <option value={position.id} key={position.id}>
                {position.posicode} · {position.name}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Pay frequency" htmlFor="employee-frequency">
          <Select
            id="employee-frequency"
            value={form.pay_frequency}
            onChange={(event) => set("pay_frequency", event.target.value)}
          >
            <option value="monthly">Monthly</option>
            <option value="weekly">Weekly</option>
          </Select>
        </Field>

        <Field label="Tax ID" htmlFor="employee-tax">
          <Input
            id="employee-tax"
            value={form.tax_id}
            onChange={(event) => set("tax_id", event.target.value)}
          />
        </Field>
        <Field label="Pension ID" htmlFor="employee-pension">
          <Input
            id="employee-pension"
            value={form.pension_id}
            onChange={(event) => set("pension_id", event.target.value)}
          />
        </Field>

        {sensitive ? (
          <>
            <Field label="Basic salary" htmlFor="employee-salary">
              <Input
                id="employee-salary"
                type="number"
                min="0"
                step="0.01"
                value={form.basic_salary}
                onChange={(event) => set("basic_salary", event.target.value)}
              />
            </Field>
            <Field label="Hourly rate" htmlFor="employee-rate">
              <Input
                id="employee-rate"
                type="number"
                min="0"
                step="0.01"
                value={form.hourly_rate}
                onChange={(event) => set("hourly_rate", event.target.value)}
              />
            </Field>
            <Field label="Bank name" htmlFor="employee-bank">
              <Input
                id="employee-bank"
                value={form.bank_name}
                onChange={(event) => set("bank_name", event.target.value)}
              />
            </Field>
            <Field label="Bank code" htmlFor="employee-bank-code">
              <Input
                id="employee-bank-code"
                value={form.bank_code}
                onChange={(event) => set("bank_code", event.target.value)}
              />
            </Field>
            <Field label="Account name" htmlFor="employee-account-name">
              <Input
                id="employee-account-name"
                value={form.account_name}
                onChange={(event) => set("account_name", event.target.value)}
              />
            </Field>
            <Field label="Account number" htmlFor="employee-account-number">
              <Input
                id="employee-account-number"
                value={form.bank_account}
                onChange={(event) => set("bank_account", event.target.value)}
              />
            </Field>
          </>
        ) : null}

        <label className="check form-span">
          <input
            type="checkbox"
            checked={form.active}
            onChange={(event) => set("active", event.target.checked)}
          />
          Active employee
        </label>
      </form>
    </Modal>
  );
}

function PositionEditor({
  position,
  onClose,
}: {
  position?: Position;
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [code, setCode] = useState(position?.posicode ?? "");
  const [name, setName] = useState(position?.name ?? "");
  const save = useMutation({
    mutationFn: () =>
      position
        ? request<Position>(`/positions/${position.id}/`, {
            method: "PATCH",
            body: JSON.stringify({ posicode: code, name }),
          })
        : request<Position>("/positions/", {
            method: "POST",
            body: JSON.stringify({ posicode: code, name }),
          }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["hr-positions"] });
      toast.push(position ? "Position updated." : "Position created.");
      onClose();
    },
  });

  return (
    <Modal
      open
      onClose={onClose}
      title={position ? "Edit position" : "New position"}
      footer={
        <>
          <Button onClick={onClose}>Cancel</Button>
          <Button
            type="submit"
            form="position-form"
            variant="primary"
            busy={save.isPending}
          >
            Save position
          </Button>
        </>
      }
    >
      <form
        id="position-form"
        className="form-grid"
        onSubmit={(event: FormEvent) => {
          event.preventDefault();
          save.mutate();
        }}
      >
        {save.isError ? (
          <div className="form-error form-span" role="alert">
            {firstError(save.error)}
          </div>
        ) : null}
        <Field label="Code" htmlFor="position-code">
          <Input
            id="position-code"
            value={code}
            onChange={(event) => setCode(event.target.value)}
            required
          />
        </Field>
        <Field label="Name" htmlFor="position-name">
          <Input
            id="position-name"
            value={name}
            onChange={(event) => setName(event.target.value)}
            required
          />
        </Field>
      </form>
    </Modal>
  );
}

function EmployeesTab({
  sensitive,
  positions,
}: {
  sensitive: boolean;
  positions: Position[];
}) {
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  const [editing, setEditing] = useState<Employee | null | undefined>(undefined);
  const search = useDebounced(query);
  const employees = useQuery({
    queryKey: ["hr-employees", page, search],
    queryFn: () =>
      getList<Employee>("/payroll-employees/", {
        page,
        page_size: 25,
        ...(search ? { search } : {}),
      }),
  });

  return (
    <Card
      title="Employee register"
      aside={
        <Button size="sm" variant="primary" onClick={() => setEditing(null)}>
          <Plus size={15} aria-hidden="true" /> New employee
        </Button>
      }
    >
      <Toolbar>
        <SearchInput value={query} onChange={setQuery} placeholder="Search staff number or name" />
        <span className="toolbar-count">{employees.data?.total ?? 0} employees</span>
      </Toolbar>
      {employees.isLoading ? <Loading rows={5} /> : null}
      {employees.isError ? (
        <ErrorState
          message={firstError(employees.error)}
          retry={() => void employees.refetch()}
        />
      ) : null}
      {employees.data ? (
        <>
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Staff</th>
                  <th>Position</th>
                  <th>Frequency</th>
                  {sensitive ? <th className="num">Basic salary</th> : null}
                  <th>Status</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {employees.data.data.map((employee) => (
                  <tr key={employee.id}>
                    <td>
                      <strong>{employee.full_name}</strong>
                      <div className="cell-sub mono">{employee.staff_no}</div>
                    </td>
                    <td>{employee.position_name || <span className="muted">Unassigned</span>}</td>
                    <td>{titleCase(employee.pay_frequency)}</td>
                    {sensitive ? <td className="num">{money(employee.basic_salary)}</td> : null}
                    <td>
                      {employee.active ? <Badge tone="ok">Active</Badge> : <Badge>Inactive</Badge>}
                    </td>
                    <td>
                      <Button size="sm" onClick={() => setEditing(employee)}>
                        <Pencil size={14} aria-hidden="true" /> Edit
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {!employees.data.data.length ? (
            <EmptyState title="No employees" body="Create the first employee record." />
          ) : null}
          <Pagination
            page={page}
            pageSize={25}
            total={employees.data.total}
            onPage={setPage}
          />
        </>
      ) : null}
      {editing !== undefined ? (
        <EmployeeEditor
          employee={editing ?? undefined}
          positions={positions}
          sensitive={sensitive}
          onClose={() => setEditing(undefined)}
        />
      ) : null}
    </Card>
  );
}

function PositionsTab() {
  const [editing, setEditing] = useState<Position | null | undefined>(undefined);
  const positions = useQuery({
    queryKey: ["hr-positions"],
    queryFn: () => getList<Position>("/positions/", { page_size: 200 }),
  });

  return (
    <Card
      title="Positions"
      aside={
        <Button size="sm" variant="primary" onClick={() => setEditing(null)}>
          <Plus size={15} aria-hidden="true" /> New position
        </Button>
      }
    >
      {positions.isLoading ? <Loading rows={4} /> : null}
      {positions.isError ? (
        <ErrorState
          message={firstError(positions.error)}
          retry={() => void positions.refetch()}
        />
      ) : null}
      {positions.data ? (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Code</th>
                <th>Position</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {positions.data.data.map((position) => (
                <tr key={position.id}>
                  <td className="mono">{position.posicode}</td>
                  <td>{position.name}</td>
                  <td>
                    <Button size="sm" onClick={() => setEditing(position)}>
                      <Pencil size={14} aria-hidden="true" /> Edit
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
      {editing !== undefined ? (
        <PositionEditor
          position={editing ?? undefined}
          onClose={() => setEditing(undefined)}
        />
      ) : null}
    </Card>
  );
}

function TimesheetEditor({
  employees,
  onClose,
}: {
  employees: Employee[];
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [employee, setEmployee] = useState("");
  const [start, setStart] = useState(todayISO());
  const [end, setEnd] = useState(todayISO());
  const create = useMutation({
    mutationFn: () =>
      request<Timesheet>("/timesheets/", {
        method: "POST",
        body: JSON.stringify({
          employee: Number(employee),
          period_start: start,
          period_end: end,
        }),
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["hr-timesheets"] });
      toast.push("Timesheet created.");
      onClose();
    },
  });

  return (
    <Modal
      open
      onClose={onClose}
      title="New timesheet"
      description="Start a draft period, add time entries, then submit for approval."
      footer={
        <>
          <Button onClick={onClose}>Cancel</Button>
          <Button
            type="submit"
            form="timesheet-form"
            variant="primary"
            busy={create.isPending}
            disabled={!employee}
          >
            Create timesheet
          </Button>
        </>
      }
    >
      <form
        id="timesheet-form"
        className="form-grid"
        onSubmit={(event: FormEvent) => {
          event.preventDefault();
          create.mutate();
        }}
      >
        {create.isError ? (
          <div className="form-error form-span" role="alert">
            {firstError(create.error)}
          </div>
        ) : null}
        <Field label="Employee" htmlFor="timesheet-employee" className="form-span">
          <Select
            id="timesheet-employee"
            value={employee}
            onChange={(event) => setEmployee(event.target.value)}
            required
          >
            <option value="">Choose employee</option>
            {employees.map((row) => (
              <option value={row.id} key={row.id}>
                {row.staff_no} · {row.full_name}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Period start" htmlFor="timesheet-start">
          <Input
            id="timesheet-start"
            type="date"
            value={start}
            onChange={(event) => setStart(event.target.value)}
            required
          />
        </Field>
        <Field label="Period end" htmlFor="timesheet-end">
          <Input
            id="timesheet-end"
            type="date"
            value={end}
            onChange={(event) => setEnd(event.target.value)}
            required
          />
        </Field>
      </form>
    </Modal>
  );
}

function TimeEntryEditor({
  timesheet,
  sensitive,
  onClose,
}: {
  timesheet: Timesheet;
  sensitive: boolean;
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [date, setDate] = useState(todayISO());
  const [hours, setHours] = useState("8");
  const [kind, setKind] = useState<TimeEntry["kind"]>("regular");
  const [rate, setRate] = useState("");
  const [holiday, setHoliday] = useState(false);
  const [project, setProject] = useState("");
  const [jobNo, setJobNo] = useState("");
  const create = useMutation({
    mutationFn: () => {
      const payload: Record<string, unknown> = {
        timesheet: timesheet.id,
        work_date: date,
        hours,
        kind,
        is_holiday: holiday,
        project,
        job_no: jobNo,
      };
      if (sensitive && rate) payload.rate = rate;
      return request<TimeEntry>("/time-entries/", {
        method: "POST",
        body: JSON.stringify(payload),
      });
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["hr-timesheets"] });
      toast.push("Time entry added.");
      onClose();
    },
  });

  return (
    <Modal
      open
      onClose={onClose}
      title={`Add time to ${timesheet.staff_no}`}
      footer={
        <>
          <Button onClick={onClose}>Cancel</Button>
          <Button
            type="submit"
            form="time-entry-form"
            variant="primary"
            busy={create.isPending}
          >
            Add entry
          </Button>
        </>
      }
    >
      <form
        id="time-entry-form"
        className="form-grid"
        onSubmit={(event: FormEvent) => {
          event.preventDefault();
          create.mutate();
        }}
      >
        {create.isError ? (
          <div className="form-error form-span" role="alert">
            {firstError(create.error)}
          </div>
        ) : null}
        <Field label="Work date" htmlFor="time-date">
          <Input
            id="time-date"
            type="date"
            value={date}
            onChange={(event) => setDate(event.target.value)}
            required
          />
        </Field>
        <Field label="Hours" htmlFor="time-hours">
          <Input
            id="time-hours"
            type="number"
            min="0.01"
            step="0.01"
            value={hours}
            onChange={(event) => setHours(event.target.value)}
            required
          />
        </Field>
        <Field label="Kind" htmlFor="time-kind">
          <Select
            id="time-kind"
            value={kind}
            onChange={(event) => setKind(event.target.value as TimeEntry["kind"])}
          >
            <option value="regular">Regular</option>
            <option value="ot150">Overtime 150%</option>
            <option value="ot200">Overtime 200%</option>
          </Select>
        </Field>
        {sensitive ? (
          <Field label="Rate override" htmlFor="time-rate" hint="Optional.">
            <Input
              id="time-rate"
              type="number"
              min="0"
              step="0.01"
              value={rate}
              onChange={(event) => setRate(event.target.value)}
            />
          </Field>
        ) : null}
        <Field label="Project" htmlFor="time-project">
          <Input
            id="time-project"
            value={project}
            onChange={(event) => setProject(event.target.value)}
          />
        </Field>
        <Field label="Job number" htmlFor="time-job">
          <Input
            id="time-job"
            value={jobNo}
            onChange={(event) => setJobNo(event.target.value)}
          />
        </Field>
        <label className="check form-span">
          <input
            type="checkbox"
            checked={holiday}
            onChange={(event) => setHoliday(event.target.checked)}
          />
          Public holiday
        </label>
      </form>
    </Modal>
  );
}

function TimesheetsTab({
  employees,
  sensitive,
  canApprove,
}: {
  employees: Employee[];
  sensitive: boolean;
  canApprove: boolean;
}) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [page, setPage] = useState(1);
  const [editor, setEditor] = useState(false);
  const [entryFor, setEntryFor] = useState<Timesheet | null>(null);
  const [expanded, setExpanded] = useState<number | null>(null);
  const timesheets = useQuery({
    queryKey: ["hr-timesheets", page],
    queryFn: () => getList<Timesheet>("/timesheets/", { page, page_size: 25 }),
  });
  const action = useMutation({
    mutationFn: ({ id, verb }: { id: number; verb: string }) =>
      request<Timesheet>(`/timesheets/${id}/${verb}/`, {
        method: "POST",
        body: JSON.stringify({ reason: "Returned from HR console" }),
      }),
    onSuccess: (_result, variables) => {
      void queryClient.invalidateQueries({ queryKey: ["hr-timesheets"] });
      toast.push(`Timesheet ${variables.verb}.`);
    },
  });

  return (
    <Card
      title="Time & attendance"
      aside={
        <Button size="sm" variant="primary" onClick={() => setEditor(true)}>
          <Plus size={15} aria-hidden="true" /> New timesheet
        </Button>
      }
    >
      {timesheets.isLoading ? <Loading rows={5} /> : null}
      {timesheets.isError ? (
        <ErrorState
          message={firstError(timesheets.error)}
          retry={() => void timesheets.refetch()}
        />
      ) : null}
      {timesheets.data ? (
        <>
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Staff no.</th>
                  <th>Period</th>
                  <th className="num">Hours</th>
                  <th className="num">Days</th>
                  <th>Status</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {timesheets.data.data.map((sheet) => (
                  <Fragment key={sheet.id}>
                    <tr>
                      <td className="mono">{sheet.staff_no}</td>
                      <td>
                        {formatDate(sheet.period_start)} – {formatDate(sheet.period_end)}
                      </td>
                      <td className="num">{sheet.total_hours}</td>
                      <td className="num">{sheet.worked_days}</td>
                      <td>
                        <StatusBadge status={sheet.status} />
                      </td>
                      <td>
                        <div className="row-actions">
                          <Button
                            size="sm"
                            onClick={() =>
                              setExpanded((current) =>
                                current === sheet.id ? null : sheet.id,
                              )
                            }
                          >
                            {expanded === sheet.id ? "Hide" : "Time"}
                          </Button>
                          {sheet.status === "draft" ? (
                            <Button
                              size="sm"
                              onClick={() =>
                                setEntryFor(entryFor?.id === sheet.id ? null : sheet)
                              }
                            >
                              <Plus size={13} aria-hidden="true" /> Entry
                            </Button>
                          ) : null}
                          {sheet.status === "draft" ? (
                            <Button
                              size="sm"
                              variant="primary"
                              busy={action.isPending}
                              onClick={() => action.mutate({ id: sheet.id, verb: "submit" })}
                            >
                              <Send size={13} aria-hidden="true" /> Submit
                            </Button>
                          ) : null}
                          {canApprove && sheet.status === "submitted" ? (
                            <>
                              <Button
                                size="sm"
                                variant="primary"
                                busy={action.isPending}
                                onClick={() => action.mutate({ id: sheet.id, verb: "approve" })}
                              >
                                <Check size={13} aria-hidden="true" /> Approve
                              </Button>
                              <Button
                                size="sm"
                                variant="danger"
                                busy={action.isPending}
                                onClick={() => action.mutate({ id: sheet.id, verb: "reject" })}
                              >
                                <X size={13} aria-hidden="true" /> Reject
                              </Button>
                            </>
                          ) : null}
                        </div>
                      </td>
                    </tr>
                    {expanded === sheet.id ? (
                      <tr>
                        <td colSpan={6}>
                          {sheet.entries.length ? (
                            <div className="table-wrap">
                              <table className="table table-compact">
                                <thead>
                                  <tr>
                                    <th>Date</th>
                                    <th className="num">Hours</th>
                                    <th>Kind</th>
                                    <th>Holiday</th>
                                    <th>Project</th>
                                    <th>Job</th>
                                  </tr>
                                </thead>
                                <tbody>
                                  {sheet.entries.map((entry) => (
                                    <tr key={entry.id}>
                                      <td>{formatDate(entry.work_date)}</td>
                                      <td className="num">{entry.hours}</td>
                                      <td>{titleCase(entry.kind)}</td>
                                      <td>{entry.is_holiday ? "Yes" : "No"}</td>
                                      <td>{entry.project || "-"}</td>
                                      <td>{entry.job_no || "-"}</td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            </div>
                          ) : (
                            <p className="muted body-copy">
                              No time entries yet. Add the first entry above.
                            </p>
                          )}
                        </td>
                      </tr>
                    ) : null}
                  </Fragment>
                ))}
              </tbody>
            </table>
          </div>
          {!timesheets.data.data.length ? (
            <EmptyState
              title="No timesheets"
              body="Create a timesheet to record attendance and overtime."
            />
          ) : null}
          <Pagination
            page={page}
            pageSize={25}
            total={timesheets.data.total}
            onPage={setPage}
          />
        </>
      ) : null}
      {action.isError ? <p className="form-error">{firstError(action.error)}</p> : null}
      {editor ? (
        <TimesheetEditor employees={employees} onClose={() => setEditor(false)} />
      ) : null}
      {entryFor ? (
        <TimeEntryEditor
          timesheet={entryFor}
          sensitive={sensitive}
          onClose={() => setEntryFor(null)}
        />
      ) : null}
    </Card>
  );
}

function PayslipsTab() {
  const [page, setPage] = useState(1);
  const payslips = useQuery({
    queryKey: ["hr-payslips", page],
    queryFn: () => getList<Payslip>("/payslips/", { page, page_size: 25 }),
  });

  return (
    <Card title="Payslips" aside={<Badge tone="brand">Restricted</Badge>}>
      {payslips.isLoading ? <Loading rows={5} /> : null}
      {payslips.isError ? (
        <ErrorState
          message={firstError(payslips.error)}
          retry={() => void payslips.refetch()}
        />
      ) : null}
      {payslips.data ? (
        <>
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Employee</th>
                  <th>Staff no.</th>
                  <th className="num">Gross</th>
                  <th className="num">Deductions</th>
                  <th className="num">Net</th>
                </tr>
              </thead>
              <tbody>
                {payslips.data.data.map((row) => (
                  <tr key={row.id}>
                    <td>{row.employee_name}</td>
                    <td className="mono">{row.staff_no}</td>
                    <td className="num">{money(row.gross)}</td>
                    <td className="num">{money(row.deductions)}</td>
                    <td className="num">{money(row.net)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pagination
            page={page}
            pageSize={25}
            total={payslips.data.total}
            onPage={setPage}
          />
        </>
      ) : null}
    </Card>
  );
}

function PaySetupEditor({
  employees,
  elements,
  onClose,
}: {
  employees: Employee[];
  elements: PayElement[];
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [employee, setEmployee] = useState("");
  const [element, setElement] = useState("");
  const [amount, setAmount] = useState("");
  const create = useMutation({
    mutationFn: () =>
      request<EmployeePayElement>("/employee-pay-elements/", {
        method: "POST",
        body: JSON.stringify({
          employee: Number(employee),
          element: Number(element),
          amount,
        }),
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["hr-pay-elements"] });
      toast.push("Employee pay element saved.");
      onClose();
    },
  });

  return (
    <Modal
      open
      onClose={onClose}
      title="Assign pay element"
      footer={
        <>
          <Button onClick={onClose}>Cancel</Button>
          <Button
            type="submit"
            form="pay-element-form"
            variant="primary"
            busy={create.isPending}
            disabled={!employee || !element}
          >
            Save
          </Button>
        </>
      }
    >
      <form
        id="pay-element-form"
        className="form-grid"
        onSubmit={(event: FormEvent) => {
          event.preventDefault();
          create.mutate();
        }}
      >
        {create.isError ? (
          <div className="form-error form-span" role="alert">
            {firstError(create.error)}
          </div>
        ) : null}
        <Field label="Employee" htmlFor="pay-element-employee">
          <Select
            id="pay-element-employee"
            value={employee}
            onChange={(event) => setEmployee(event.target.value)}
            required
          >
            <option value="">Choose employee</option>
            {employees.map((row) => (
              <option value={row.id} key={row.id}>
                {row.staff_no} · {row.full_name}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Element" htmlFor="pay-element-code">
          <Select
            id="pay-element-code"
            value={element}
            onChange={(event) => setElement(event.target.value)}
            required
          >
            <option value="">Choose element</option>
            {elements.map((row) => (
              <option value={row.id} key={row.id}>
                {row.code} · {row.name}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Amount" htmlFor="pay-element-amount" className="form-span">
          <Input
            id="pay-element-amount"
            type="number"
            min="0"
            step="0.01"
            value={amount}
            onChange={(event) => setAmount(event.target.value)}
            required
          />
        </Field>
      </form>
    </Modal>
  );
}

function PaySetupTab({
  employees,
}: {
  employees: Employee[];
}) {
  const [editor, setEditor] = useState(false);
  const [page, setPage] = useState(1);
  const rows = useQuery({
    queryKey: ["hr-pay-elements", page],
    queryFn: () =>
      getList<EmployeePayElement>("/employee-pay-elements/", { page, page_size: 25 }),
  });
  const elements = useQuery({
    queryKey: ["hr-pay-element-definitions"],
    queryFn: () => getList<PayElement>("/pay-elements/", { page_size: 200 }),
    enabled: editor,
  });

  return (
    <Card
      title="Employee pay setup"
      aside={
        <Button size="sm" variant="primary" onClick={() => setEditor(true)}>
          <Plus size={15} aria-hidden="true" /> Assign element
        </Button>
      }
    >
      {rows.isLoading ? <Loading rows={4} /> : null}
      {rows.isError ? (
        <ErrorState message={firstError(rows.error)} retry={() => void rows.refetch()} />
      ) : null}
      {rows.data ? (
        <>
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Employee</th>
                  <th>Element</th>
                  <th className="num">Amount</th>
                </tr>
              </thead>
              <tbody>
                {rows.data.data.map((row) => (
                  <tr key={row.id}>
                    <td>{row.employee_name}</td>
                    <td>
                      <span className="mono">{row.element_code}</span> · {row.element_name}
                    </td>
                    <td className="num">{money(row.amount)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pagination
            page={page}
            pageSize={25}
            total={rows.data.total}
            onPage={setPage}
          />
        </>
      ) : null}
      {editor ? (
        <PaySetupEditor
          employees={employees}
          elements={elements.data?.data ?? []}
          onClose={() => setEditor(false)}
        />
      ) : null}
    </Card>
  );
}

function ProvisionsTab({ employees }: { employees: Employee[] }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [editor, setEditor] = useState(false);
  const [page, setPage] = useState(1);
  const [timesheet, setTimesheet] = useState("");
  const [dailyRate, setDailyRate] = useState("");
  const [asOf, setAsOf] = useState(todayISO());
  const [kind, setKind] = useState("leave");
  const provisions = useQuery({
    queryKey: ["hr-provisions", page],
    queryFn: () => getList<Provision>("/provisions/", { page, page_size: 25 }),
  });
  const approvedTimesheets = useQuery({
    queryKey: ["hr-timesheets", "approved-options"],
    queryFn: () => getList<Timesheet>("/timesheets/", { status: "approved", page_size: 100 }),
    enabled: editor,
  });
  const employeeName = new Map(employees.map((row) => [row.id, row.full_name]));

  const create = useMutation({
    mutationFn: () =>
      request<Provision>("/provisions/", {
        method: "POST",
        body: JSON.stringify({
          timesheet: Number(timesheet),
          daily_rate: dailyRate,
          as_of: asOf,
          kind,
        }),
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["hr-provisions"] });
      toast.push("Provision accrued.");
      setEditor(false);
    },
  });

  return (
    <>
      <Card
        title="Leave & workforce provisions"
        aside={
          <Button size="sm" variant="primary" onClick={() => setEditor(true)}>
            <Plus size={15} aria-hidden="true" /> Accrue provision
          </Button>
        }
      >
        {provisions.isLoading ? <Loading rows={4} /> : null}
        {provisions.isError ? (
          <ErrorState
            message={firstError(provisions.error)}
            retry={() => void provisions.refetch()}
          />
        ) : null}
        {provisions.data ? (
          <>
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Employee</th>
                    <th>Kind</th>
                    <th className="num">Days</th>
                    <th className="num">Daily rate</th>
                    <th className="num">Amount</th>
                    <th>As of</th>
                  </tr>
                </thead>
                <tbody>
                  {provisions.data.data.map((row) => (
                    <tr key={row.id}>
                      <td>{employeeName.get(row.employee) ?? `Employee ${row.employee}`}</td>
                      <td>{titleCase(row.kind)}</td>
                      <td className="num">{row.days}</td>
                      <td className="num">{money(row.rate)}</td>
                      <td className="num">{money(row.amount)}</td>
                      <td>{formatDate(row.as_of)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {!provisions.data.data.length ? (
              <EmptyState
                title="No provisions"
                body="Accrue leave or workforce provisions from an approved timesheet."
              />
            ) : null}
            <Pagination
              page={page}
              pageSize={25}
              total={provisions.data.total}
              onPage={setPage}
            />
          </>
        ) : null}
      </Card>

      {editor ? (
        <Modal
          open
          onClose={() => setEditor(false)}
          title="Accrue provision"
          footer={
            <>
              <Button onClick={() => setEditor(false)}>Cancel</Button>
              <Button
                type="submit"
                form="provision-form"
                variant="primary"
                busy={create.isPending}
                disabled={!timesheet}
              >
                Save provision
              </Button>
            </>
          }
        >
          <form
            id="provision-form"
            className="form-grid"
            onSubmit={(event: FormEvent) => {
              event.preventDefault();
              create.mutate();
            }}
          >
            {create.isError ? (
              <div className="form-error form-span" role="alert">
                {firstError(create.error)}
              </div>
            ) : null}
            <Field label="Approved timesheet" htmlFor="provision-timesheet" className="form-span">
              <Select
                id="provision-timesheet"
                value={timesheet}
                onChange={(event) => setTimesheet(event.target.value)}
                required
              >
                <option value="">Choose timesheet</option>
                {(approvedTimesheets.data?.data ?? []).map((row) => (
                  <option value={row.id} key={row.id}>
                    {row.staff_no} · {formatDate(row.period_start)} – {formatDate(row.period_end)}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="Daily rate" htmlFor="provision-rate">
              <Input
                id="provision-rate"
                type="number"
                min="0"
                step="0.01"
                value={dailyRate}
                onChange={(event) => setDailyRate(event.target.value)}
                required
              />
            </Field>
            <Field label="As of" htmlFor="provision-date">
              <Input
                id="provision-date"
                type="date"
                value={asOf}
                onChange={(event) => setAsOf(event.target.value)}
                required
              />
            </Field>
            <Field label="Kind" htmlFor="provision-kind" className="form-span">
              <Select
                id="provision-kind"
                value={kind}
                onChange={(event) => setKind(event.target.value)}
              >
                <option value="leave">Leave</option>
                <option value="gratuity">Gratuity</option>
                <option value="other">Other</option>
              </Select>
            </Field>
            <Textarea rows={2} className="form-span" readOnly value="Provision amounts flow to the finance ledger." />
          </form>
        </Modal>
      ) : null}
    </>
  );
}

export function HrPage() {
  const { user } = useAuth();
  const [params, setParams] = useSearchParams();
  const officer = isHrOnly(user);
  const sensitive = !officer;
  const canApprove = can(user, HR_MANAGER_ROLES);
  const tabs = officer ? BASE_TABS : [...BASE_TABS, ...MANAGER_TABS];
  const rawTab = params.get("tab");
  const tab: Tab = tabs.some((item) => item.id === rawTab) ? (rawTab as Tab) : "employees";

  const employees = useQuery({
    queryKey: ["hr-employees", "options"],
    queryFn: () => getList<Employee>("/payroll-employees/", { page_size: 200 }),
    enabled: tab === "timesheets" || tab === "pay-setup" || tab === "provisions",
  });
  const positions = useQuery({
    queryKey: ["hr-positions", "options"],
    queryFn: () => getList<Position>("/positions/", { page_size: 200 }),
    enabled: tab === "employees",
  });

  function setTab(next: Tab) {
    const copy = new URLSearchParams(params);
    copy.set("tab", next);
    setParams(copy, { replace: true });
  }

  const menu = employees.data?.data ?? [];

  return (
    <>
      <PageHeader
        eyebrow="People"
        title="HR workspace"
        description={
          officer
            ? "Maintain employee records and timekeeping without access to payroll-confidential data."
            : "Maintain employees, approve time, manage pay setup and oversee workforce provisions."
        }
        actions={
          <Badge tone={officer ? "neutral" : "brand"}>
            {officer ? "HR Officer" : "HR Manager access"}
          </Badge>
        }
      />

      <div className="tabs" role="tablist" aria-label="HR sections">
        {tabs.map((item) => (
          <button
            key={item.id}
            type="button"
            role="tab"
            aria-selected={tab === item.id}
            className={tab === item.id ? "tab active" : "tab"}
            onClick={() => setTab(item.id)}
          >
            {item.label}
          </button>
        ))}
      </div>

      <div className="mini-grid">
        <div className="mini-stat">
          <span>Employees</span>
          <strong>{employees.data?.total ?? "—"}</strong>
        </div>
        <div className="mini-stat">
          <span>Positions</span>
          <strong>{positions.data?.total ?? "—"}</strong>
        </div>
        <div className="mini-stat">
          <span>Pay access</span>
          <strong>{officer ? "Restricted" : "Manager"}</strong>
        </div>
        <div className="mini-stat">
          <span>Timesheet approval</span>
          <strong>{canApprove ? "Allowed" : "Not permitted"}</strong>
        </div>
      </div>

      {tab === "employees" ? (
        <EmployeesTab sensitive={sensitive} positions={positions.data?.data ?? []} />
      ) : null}
      {tab === "positions" ? <PositionsTab /> : null}
      {tab === "timesheets" ? (
        <TimesheetsTab
          employees={menu}
          sensitive={sensitive}
          canApprove={canApprove}
        />
      ) : null}
      {tab === "payslips" ? <PayslipsTab /> : null}
      {tab === "pay-setup" ? <PaySetupTab employees={menu} /> : null}
      {tab === "provisions" ? <ProvisionsTab employees={menu} /> : null}

      {officer ? (
        <p className="hint">
          Need payroll or payslip information? Ask the HR Manager or the finance team.
        </p>
      ) : null}
    </>
  );
}
