# Deployment guide

This guide covers a production deployment of the Django/DRF backend. The
application is stateless; PostgreSQL, Redis, S3/MinIO and SMTP are external
services.

## 1. Prerequisites

- Python 3.12+ or Docker 24+ / Compose v2
- PostgreSQL 16+ with a dedicated database and role
- Redis 7+ (Celery broker/result backend and shared cache)
- S3-compatible object storage (AWS S3 or MinIO)
- SMTP relay with TLS
- TLS-terminating reverse proxy (nginx, Caddy, ALB, …)

## 2. Required configuration

Create a `.env` (never commit it) or inject variables through your platform.
Start from `.env.example` and set at minimum:

```dotenv
DJANGO_SETTINGS_MODULE=config.settings.prod
SECRET_KEY=<long random value>
DEBUG=false
ALLOWED_HOSTS=tcms.example.com
CSRF_TRUSTED_ORIGINS=https://tcms.example.com
SECURE_SSL_REDIRECT=true
USE_X_FORWARDED_PROTO=true

USE_SQLITE=false
DB_NAME=tcms
DB_USER=tcms
DB_PASSWORD=<strong password>
DB_HOST=<database host>
DB_PORT=5432

CELERY_BROKER_URL=redis://<redis host>:6379/0
CELERY_RESULT_BACKEND=redis://<redis host>:6379/1
REDIS_CACHE_URL=redis://<redis host>:6379/2

EMAIL_HOST=<smtp host>
EMAIL_PORT=587
EMAIL_HOST_USER=<smtp user>
EMAIL_HOST_PASSWORD=<smtp password>
EMAIL_USE_TLS=true
DEFAULT_FROM_EMAIL=no-reply@example.com

USE_S3_STORAGE=true
AWS_ACCESS_KEY_ID=<key>
AWS_SECRET_ACCESS_KEY=<secret>
AWS_STORAGE_BUCKET_NAME=tcms-documents
AWS_S3_REGION_NAME=<region>
AWS_S3_ENDPOINT_URL=<optional MinIO endpoint>
```

Deployment decisions that should be confirmed before go-live:

- `BILLING_TAX_PCT` — VAT rate applied to invoices (default `0` is safe).
- `CERTIFICATE_*` — organisation name, logo/signature/seal storage keys and
  optional verification URL.
- `PAYROLL_*` — pension rates, annual relief and GL account codes. Run
  `python manage.py payroll_check` after migrating; it fails if bands, rates or
  GL accounts are missing.
- `ENFORCE_FACILITY_CAPACITY` / `ENFORCE_VENUE_EXCLUSIVITY` — keep both `true`
  unless operations explicitly schedules concurrent courses in one venue.

## 3. Build and release

### Docker (recommended)

```bash
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml run --rm web python manage.py migrate
docker compose -f docker-compose.prod.yml run --rm web python manage.py seed_roles
docker compose -f docker-compose.prod.yml up -d
```

The web container runs migrations on start (`RUN_MIGRATIONS=1`) and then serves
Gunicorn on `127.0.0.1:8000`. The frontend container builds the Vite console and
serves it with nginx on `127.0.0.1:8080`, proxying `/api/`, `/admin/`, `/portal/`,
`/static/` and `/media/` to the web service. Point the TLS reverse proxy at the
frontend container, not directly at Gunicorn. Workers and beat are separate
services. Do **not** run `seed_data`/`seed_demo` against production unless the
business explicitly wants demo/reference data.

### Bare metal / PaaS

```bash
pip install -r requirements.txt
python manage.py collectstatic --noinput
python manage.py migrate
python manage.py seed_roles
gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 3 --timeout 60
celery -A config worker -l info
celery -A config beat -l info
```

Serve `staticfiles/` through WhiteNoise (already configured) or the reverse
proxy. Uploaded media goes to S3/MinIO; local `media/` is only a fallback.

### Staff console without Docker

Build the Vite app and publish the static output:

```bash
cd frontend
npm ci
npm run build
# copy frontend/dist/ to the web root exposed by the reverse proxy
```

The console calls the API on its own origin, so no API base URL is compiled in.
Terminate TLS at the proxy and route `/api/`, `/admin/`, `/portal/`, `/static/`
and `/media/` to Gunicorn while serving `frontend/dist/` at `/`. For client-side
routes, fall back to `index.html`:

```nginx
root /srv/tcms-console;
location / {
    try_files $uri $uri/ /index.html;
}
location /api/ {
    proxy_pass http://127.0.0.1:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
}
location /admin/ { proxy_pass http://127.0.0.1:8000; }
location /portal/ { proxy_pass http://127.0.0.1:8000; }
location /static/ { proxy_pass http://127.0.0.1:8000; }
location /media/ { proxy_pass http://127.0.0.1:8000; }
```

Re-run `npm ci && npm run build` on every release; `dist/` is not committed.

## 4. Reverse proxy and TLS

Forward `Host`, `X-Forwarded-Proto` and `X-Forwarded-For`. Set
`USE_X_FORWARDED_PROTO=true` and the correct `DRF_NUM_PROXIES` only when the
proxy overwrites those headers. Redirect HTTP to HTTPS at the proxy; the app
also enforces `SECURE_SSL_REDIRECT`.

Health probe: `GET /api/v1/health/` returns `200` when the database and cache
are reachable, `503` otherwise.

## 5. Post-deploy verification

```bash
python manage.py check --deploy
python manage.py showmigrations --plan
python manage.py payroll_check
python manage.py spectacular --file /tmp/schema.yml --validate
curl -fsS https://tcms.example.com/api/v1/health/
python scripts/smoke.py --base-url https://tcms.example.com
```

Then sign in as the seeded System Admin, create real staff users/roles, and
disable or rotate the bootstrap admin password.

## 6. Upgrades and rollback

1. Take a database backup (see `docs/OPERATIONS.md`).
2. Pull the new image/code and run `python manage.py migrate`.
3. Restart web, worker and beat together.
4. Run the health probe and smoke test.
5. If the release is faulty, redeploy the previous image. Database migrations
   are not automatically reversible; restore the backup if a migration must be
   rolled back.

## 7. Security checklist

- Real `SECRET_KEY`, unique per environment; never reuse the dev key.
- `DEBUG=false`, restrictive `ALLOWED_HOSTS` and HTTPS-only cookies.
- Database/Redis not exposed publicly; strong credentials and network ACLs.
- S3 bucket private; generate signed URLs for document delivery.
- SMTP credentials stored in a secret manager, not in git.
- Rotate bootstrap admin credentials; enforce least-privilege roles.
- Keep `pip-audit` green and patch runtime dependencies regularly.
- Monitor failed logins, outbox failures and certificate/payroll job errors.
