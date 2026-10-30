# Load test (k6)

Prerequisites: staging with Postgres, Redis cache, Celery worker and
`SEED_DEMO` loaded. API login is rate-limited to 10/min, so the script logs in
**once** in `setup()` and reuses the token (24 h TTL).

## Run

```bash
# Linux/macOS (or Windows with k6 installed)
BASE_URL=https://staging.example.com \
API_USERNAME=demo_accounts API_PASSWORD=demo12345 \
k6 run scripts/load/k6.js --summary-export load-results.json
```

Use `--insecure-skip-tls-verify` only if staging uses a self-signed certificate.
The run lasts ~14 minutes and ramps 100 public + 40 API virtual users.

## What it covers

| Scenario | Paths | Threshold |
|---|---|---|
| `public_browse` | `/portal/`, register, login, resend | p95 < 300 ms |
| `api_reads` | companies, courses, sessions | p95 < 300 ms |

Overall error rate must stay below 0.5%. Portal authenticated pages and API
writes are exercised by UAT and the automated suite; add them here after UAT
data and write-safe accounts are agreed. Portal login throttling (10 attempts
per 5 min per IP+email) makes it unsuitable for high-concurrency login tests
without a staging-specific override.

## Evidence to record

- k6 summary export (`load-results.json`) and console summary.
- CPU/memory, DB connections and Redis/queue depth from monitoring.
- p50/p95/p99, error rate, slowest endpoints.
- Any N+1 queries from Django Debug Toolbar / `django-silk` or DB logs.
- Soak: repeat the steady state for 2 h and confirm no memory growth.
- Pass/fail against the NFR table in `tcms-design/05-hardening.md` §6.
