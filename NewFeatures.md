# New Features Implementation Plan

## Goal

Complete the staff console by integrating three areas that currently exist only
partially or behind the API:

- **Finance and payroll** under one Finance workspace.
- **HR/people operations** with two levels of access.
- **Administrative capabilities** that already have backend endpoints but no UI.

The frontend and backend must enforce the same permissions. Hiding a UI element
is never the only control.

## Role Model

Add two roles to `RoleCode`:

| ID | Code | Label |
| --- | --- | --- |
| 13 | `HR_MANAGER` | HR Manager |
| 14 | `HR_OFFICER` | HR Officer |

Workflow routing is unchanged. `ANY_ROLE` automatically includes the new roles,
so every existing use must be reviewed for unintended financial access.

### HR Manager

- Read/write employees and employment details.
- See and edit salary, hourly rate, bank details, tax ID, pension ID and pay
  frequency.
- Manage employee pay elements and provisions.
- Read payslips.
- Create, edit, submit and approve/reject timesheets.
- Read employee-linked learners but not learner documents.
- No company financial totals, corporate account balances or invoice queues.

### HR Officer

- Read/write employees except sensitive pay and banking fields.
- See `tax_id`, `pension_id` and `pay_frequency`.
- Cannot see `basic_salary`, `hourly_rate`, `bank_name`, `bank_code`,
  `account_name` or `bank_account`.
- Cannot access payslips, pay elements, tax bands, provisions or payment files.
- Create, edit and submit timesheets; cannot approve/reject.
- Cannot read or set `TimeEntry.rate`.
- Read employee-linked learners but not learner documents.
- No company financial data.

### Positions

`Employee.position` becomes a foreign key to `reference.Position`, separate
from login roles. Seed:

- `POS011` — HR Manager
- `POS012` — HR Officer / Generalist

## Backend Work

### 1. Enums and seeds

- Add `HR_MANAGER` and `HR_OFFICER` to `apps/common/enums.py`.
- Update role docstrings from 12 to 14 roles.
- Update `seed_roles.py` help text; enum iteration seeds both new roles.
- Add `POS011` and `POS012` to `seed_data.py`.
- Add `Employee.position` in `apps/payroll/models.py`.
- Generate `apps/payroll/migrations/0004_employee_position.py`.

### 2. Payroll privacy

- Keep existing finance `READ`/`WRITE` role sets for GL and pay runs.
- Add manager/officer employee serializer classes:
  - Manager serializer includes all fields plus position.
  - Officer serializer excludes salary, rates and bank fields.
  - A shared base keeps tax ID, pension ID and pay frequency.
- Select the serializer by actor role on employee list/retrieve/write.
- Deny officer writes to hidden fields by omission from the serializer.
- Add `EmployeePayElementSerializer` and viewset:
  - Route: `/api/v1/employee-pay-elements/`.
  - Read/write: System Admin, Admin, Accounts, MD, HR Manager.
  - Employee officer access is denied.
- Timesheets:
  - HR Manager and HR Officer can read/create/update/submit.
  - Approve/reject only for System Admin, Admin, MD and HR Manager.
  - Officer `TimeEntry` serializer omits `rate`.
- Payslips, pay elements, tax bands, provisions and payment files stay
  finance-only plus HR Manager where specified above.

### 3. Learner access

- Split learner roles into read and write sets.
- HR Manager and HR Officer get learner read access for employee linking.
- Learner documents remain inaccessible to both HR roles.

### 4. Reporting

- Make `ReportDefSerializer.roles` writable for System Admin.
- Keep report definitions/read access to current reporting roles.
- Zero or omit finance fields for HR users in `build_dashboard()`:
  - outstanding invoice count/total
  - collected revenue
  - unpaid invoice queue
  - revenue values in trend data
- Keep operational KPIs available to HR.

### 5. Billing privacy

- Replace `CorporateAccountViewSet.required_roles = ANY_ROLE` with the original
  non-HR staff roles.

### 6. Tests

Cover:

- Role and position seeds.
- Officer field omission and hidden-field write rejection.
- Officer pay-element/payslip/provision/tax-band/payment-file 403s.
- Officer timesheet submit success and approve/reject denial.
- Manager sensitive access and timesheet approval.
- HR denial on corporate accounts.
- HR dashboard finance zeroing.
- Multi-role precedence.
- Report role writes.

## Frontend Work

### Data and navigation

- Add both HR roles to `RoleCode`, `ROLE_LABELS`, `ROLE_IDS` and
  `ROLE_MANUALS`.
- Add permission groups for finance, HR manager and HR officer.
- Consolidate `AXIS_GROUPS` as the single navigation source for sidebar, search
  and dashboard home tiles.
- Add People, Finance and Administration groups.
- Add lazy routes and role guards in `App.tsx`.

### Finance workspace

`/finance` tabs:

- Overview
- Chart of accounts
- Journals and trial balance
- Pay runs
- Payslips
- Payment files
- Pay policy / tax bands

Billing remains a separate receivables page linked from the Finance group.

### HR workspace

`/hr` tabs:

- Employees
- Positions
- Time and attendance
- Manager only: pay setup, payslips, provisions

### Administrative workspaces

- `/notifications`: notification list and templates.
- `/documents`: document registry.
- `/audit`: audit events.
- `/workflow-admin`: workflow statuses and approvals.
- `/integration`: outbox, webhook deliveries, external refs and seed markers.
- `/report-access`: report definitions and role assignment.
- Scheduling gains venues and instructors tabs.
- Certificates gains a System Admin certificate-sequence tab.

### Dashboard

- Hide finance KPIs, the outstanding-value mini-stat, invoice queue and invoice
  contribution to queue totals from both HR roles.

## Verification

```text
python manage.py test
ruff check .
python manage.py makemigrations --check --dry-run
python manage.py spectacular --file schema.yml --validate
cd frontend
npm run typecheck
npm run lint
npm run build
```

## Acceptance Criteria

- HR Officer can manage people and submit timesheets without seeing any salary,
  bank, payslip, pay-element or provision data.
- HR Manager can manage sensitive pay setup and approve timesheets but cannot run
  payroll.
- Neither HR role sees company financial totals or receivables.
- Finance can use one workspace for GL, payroll and receivables.
- All previously API-only administrative capabilities have usable UI.
- Backend checks, tests, schema validation and frontend build pass.

## Implementation status (13 November 2026)

Delivered:

- HR Manager and HR Officer roles, position seeds, HR-safe serializers and
  deny-by-default API checks.
- Finance workspace (`/finance`), HR workspace (`/hr`), six administrative
  workspaces, scheduling venues/instructors tabs and System Admin certificate
  sequences.
- Consolidated `AXIS_GROUPS` navigation, dashboard HR finance suppression and
  HR-aware manual entries.
- Demo seed users `demo_hr_manager` and `demo_hr_officer`, plus automated
  `seed_demo` smoke coverage for HR, Finance and System Admin workspaces.
- Report-definition role assignment tests and multi-role precedence tests.

Verified:

- `python manage.py test` — 322 tests passed.
- `ruff check .` — clean.
- `python manage.py makemigrations --check --dry-run` — no changes.
- `python manage.py spectacular --file schema.yml --validate` — valid.
- `npm run typecheck`, `npm run lint`, `npm run build` — passed.
