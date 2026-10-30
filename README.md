# TCMS — Training Centre Management System

Django + DRF backend for a maritime/HSE training centre: learner and corporate
records, scheduling and seat allocation, medicals, delivery, certification,
billing, payroll, reporting, notifications and a learner/employer portal.

- Python 3.12+ (Django 6.1, DRF 3.18)
- PostgreSQL 16+ in production (SQLite for zero-setup development)
- Celery + Redis for background work; S3/MinIO for document storage
- ReportLab certificate rendering, DRF token auth, deny-by-default RBAC

## Quick start (local, SQLite)

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
source .venv/bin/activate
pip install -r requirements-dev.txt

cp .env.example .env
# The example uses USE_SQLITE=true; keep it for the fastest start.
python manage.py migrate
python manage.py seed_roles
python manage.py seed_data
python manage.py runserver
```

`seed_roles` prints the generated System Admin password once. The API is served
under `/api/v1/`; Swagger is at `/api/schema/swagger-ui/` while `DEBUG=true` or
`EXPOSE_API_DOCS=true`. The portal is at `/portal/`.

### Local PostgreSQL

Set these in `.env` (and create the database first):

```dotenv
USE_SQLITE=false
DB_NAME=tcms
DB_USER=tcms
DB_PASSWORD=change-me
DB_HOST=127.0.0.1
DB_PORT=5432
```

Then `python manage.py migrate`. Tests create and destroy a `test_tcms`
database automatically.

## Common commands

| Task | Command |
| --- | --- |
| Apply migrations | `python manage.py migrate` |
| Seed roles + workflow statuses | `python manage.py seed_roles` |
| Seed reference/catalogue data | `python manage.py seed_data` |
| Demo world (non-production) | `python manage.py seed_demo` |
| Run tests | `python manage.py test` |
| Lint | `ruff check .` |
| Migration drift | `python manage.py makemigrations --check --dry-run` |
| OpenAPI schema | `python manage.py spectacular --file schema.yml --validate` |
| Full verification | `scripts/verify.ps1` (Windows) / `scripts/verify.sh` |
| Payroll config check | `python manage.py payroll_check` |
| Production deploy check | `python manage.py check --deploy` |

## Configuration

All runtime configuration is environment-driven; see `.env.example` for the full
list. The settings that most often need a deployment decision:

| Variable | Purpose | Default |
| --- | --- | --- |
| `BILLING_TAX_PCT` | VAT applied to invoice lines | `0` |
| `ENFORCE_FACILITY_CAPACITY` | Layer 1 venue throughput cap | `true` |
| `ENFORCE_VENUE_EXCLUSIVITY` | Layer 2 one-session-per-venue rule | `true` |
| `CERTIFICATE_ORG_NAME` / `CERTIFICATE_LOGO_KEY` | Certificate branding | TASL text fallback |
| `CERTIFICATE_SIGNATORY_NAME` / `CERTIFICATE_SIGNATORY_TITLE` | Signature block | Managing Director |
| `CERTIFICATE_VERIFY_URL` | Optional footer verification link | empty |
| `PAYROLL_*` | Pension rates, PAYE relief and GL mappings | CPA/Paye defaults |

Certificate logos, signatures and seals are storage keys (local `media/` or
S3/MinIO). Missing artwork is replaced with drawn text/line fallbacks, so a
deployment never fails to produce a certificate PDF. A PDF already stored at
`Certificate.object_key` is always served unchanged.

## Docker

`docker-compose.yml` is the self-contained local/staging stack (Postgres, Redis,
MinIO, Mailpit, web, worker, beat). It uses `config.settings.prod`, so set a real
`SECRET_KEY` in `.env` before starting.

```bash
docker compose up --build
```

`docker-compose.prod.yml` is the production template. It expects external
PostgreSQL, Redis, S3/MinIO and SMTP; only the web port is bound (to loopback)
for a TLS-terminating reverse proxy. See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

## Testing

- `python manage.py test` runs the full suite (SQLite by default, PostgreSQL when
  `USE_SQLITE=false`).
- CI runs the suite on both SQLite and PostgreSQL, lints, checks migrations,
  validates the OpenAPI schema, runs `check --deploy` with production settings
  and audits pinned dependencies with `pip-audit`.
- `scripts/verify.ps1` / `scripts/verify.sh` reproduce the release gate locally.

## Project layout

```
apps/            Domain apps (accounts, learners, scheduling, certification, …)
config/          Settings (base/dev/prod) and URL/Celery configuration
scripts/         Verification, smoke test and container entrypoint
docs/            Deployment and operations runbooks
schema.yml       Committed OpenAPI schema
```

## Operations and deployment

- [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) — provisioning, environment, release
  and rollback.
- [docs/OPERATIONS.md](docs/OPERATIONS.md) — health probes, background jobs,
  backups, payroll/VAT/certificate configuration and incident runbook.
