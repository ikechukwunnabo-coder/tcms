# Operations runbook

## Health and monitoring

| Probe | Expected |
| --- | --- |
| `GET /api/v1/health/` | `200` with `database` and `cache` both `ok`; `503` otherwise |
| `GET /api/v1/integration/health/` | Outbox backlog/dispatch health (authenticated) |
| `GET /` | Staff console static shell (`200`) |
| `GET /admin/` | Django admin reachable (staff only) |

Alert on: health `503`, sustained 5xx rate, Celery queue depth, outbox events in
`failed`, certificate batch `failed`, and payroll/payslip generation errors.

Logs are JSON on stdout in production. Keep web, worker and beat logs; include a
request/correlation id where the reverse proxy provides one.

## Background jobs (Celery beat)

| Task | Schedule | Purpose |
| --- | --- | --- |
| `apps.integration.tasks.dispatch_outbox` | every 60 s | Deliver outbox webhooks |
| `apps.certification.tasks.send_due_reminders` | hourly | Certificate-expiry reminders |

Run at least one worker and exactly one beat instance. If beat is down, outbox
delivery and reminders pause; bookings and certificates still work.

## Backups and restore

- **PostgreSQL**: nightly `pg_dump -Fc` plus WAL archiving if point-in-time
  recovery is required. Retain at least 30 days off-host.
- **Object storage**: enable bucket versioning (or replicate the bucket). The
  database references object keys; losing the bucket breaks certificate and
  document downloads.
- **Redis**: no backup needed (cache/broker), but persist queues only if you
  accept the operational trade-off.
- Test a restore quarterly: restore the dump into a scratch database, run
  `python manage.py migrate --check`, and verify `/api/v1/health/`.

## Payroll configuration

PAYE bands are seeded by migration `payroll.0003_reference_data` (Nigeria Tax Act
2025, effective 2026-01-01). Pension rates, annual relief and GL account codes
come from settings. Before each tax year or parallel run:

```bash
python manage.py payroll_check --date 2026-06-30
```

The command reports missing bands, gaps/non-contiguous bands, out-of-range
pension rates and missing GL accounts. Finance must confirm the rates and codes;
the application validates that they are internally consistent, not that they are
the legally correct values.

## HR access review

Two roles carry people operations, and both must be reviewed together with the
user's other roles:

- `hr_officer` — employee and position maintenance, timesheet preparation and
  submission. The API omits salary, hourly rate and bank fields, rejects writes
  to them, and returns `403` for payslips, pay elements, employee pay elements,
  provisions, tax bands, payment files and pay runs.
- `hr_manager` — everything an HR Officer can do, plus sensitive pay setup,
  employee pay elements, provisions, payslip reads and timesheet approval. HR
  Managers cannot run payroll, read payment files/tax bands/pay elements or see
  accounts/corporate-account balances.

Neither role may read corporate accounts or receivables, and both are excluded
from revenue KPIs and unpaid-invoice queues. If a user also holds a finance or
admin role, the broader role wins; verify this deliberately during access
reviews. Run `python manage.py test apps.integration.tests.DemoRoleSmokeTests`
to exercise the seeded end-to-end role matrix.

## Billing/VAT

Invoice tax is read from `BILLING_TAX_PCT` at creation time. Set the confirmed
rate before issuing invoices; changing it does not rewrite existing invoices.
Re-issue or credit-note any invoice created with the wrong rate.

## Scheduling capacity

Capacity is enforced in three layers:

1. venue throughput (`ENFORCE_FACILITY_CAPACITY`) — concurrent sessions at a
   venue may not exceed `Venue.capacity`;
2. venue exclusivity (`ENFORCE_VENUE_EXCLUSIVITY`) — one live session per venue
   at a time;
3. session seats with `reserve_pct` headroom for carry-forward.

If operations deliberately run parallel courses in one hall, disable layers 1–2
in that environment and document why. Existing sessions are not re-validated;
the rules apply when a booking is confirmed or carried forward.

## Certificates

Certificate PDFs are rendered on demand with ReportLab and stored artefacts at
`Certificate.object_key` take precedence. To customise branding, upload artwork
to the configured storage and set:

```dotenv
CERTIFICATE_ORG_NAME=...
CERTIFICATE_ORG_ADDRESS=...
CERTIFICATE_LOGO_KEY=branding/logo.png
CERTIFICATE_SIGNATORY_NAME=...
CERTIFICATE_SIGNATORY_TITLE=...
CERTIFICATE_VERIFY_URL=https://tcms.example.com/verify
```

Signature and seal images are used only when the certificate has
`signature_applied` / `seal_applied` and the corresponding storage key is set;
otherwise the PDF draws labelled fallbacks.

## Common incidents

| Symptom | Check |
| --- | --- |
| Health `database: error` | Postgres reachable, credentials, connection limits |
| Health `cache: error` | Redis reachable, `REDIS_CACHE_URL` |
| Emails not delivered | SMTP credentials/TLS, `DEFAULT_FROM_EMAIL`, provider logs |
| Certificates missing | Object storage keys, bucket permissions, `USE_S3_STORAGE` |
| Outbox events stuck | Worker/beat running, `OUTBOX_WEBHOOK_URLS`, signing secret |
| Logins throttled | `API_LOGIN_RATE`, `ADMIN_LOGIN_RATE_*`, shared cache health |
| Certificate PDF 500 | ReportLab installed, logo/signature storage keys readable |

## Routine maintenance

- Rotate staff who leave; deactivate rather than delete users to preserve audit
  history.
- Review `audit_event` for failed logins and privileged changes.
- Run `python manage.py check --deploy` after configuration changes.
- Patch dependencies monthly and after security advisories; CI runs
  `pip-audit`.
- Verify certificate expiry reminders are being sent and corporate ZIP batches
  are delivered.
