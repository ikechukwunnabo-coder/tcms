// TCMS staging load test (k6). See ./README.md for the run procedure.
//
//   BASE_URL=https://staging.example.com \
//   API_USERNAME=demo_accounts API_PASSWORD=demo12345 \
//   k6 run scripts/load/k6.js --summary-export results.json
import http from 'k6/http';
import { check, fail, sleep } from 'k6';

const BASE = (__ENV.BASE_URL || 'http://127.0.0.1:8000').replace(/\/$/, '');
const API_USERNAME = __ENV.API_USERNAME || 'demo_accounts';
const API_PASSWORD = __ENV.API_PASSWORD || 'demo12345';

const PUBLIC_PATHS = [
  '/portal/',
  '/portal/register/',
  '/portal/registered/',
  '/portal/login/',
  '/portal/resend-verification/email/',
];

const API_PATHS = ['/api/v1/companies/', '/api/v1/courses/', '/api/v1/sessions/'];

export const options = {
  scenarios: {
    public_browse: {
      executor: 'ramping-vus',
      exec: 'publicBrowse',
      startVUs: 0,
      stages: [
        { duration: '3m', target: 100 },
        { duration: '10m', target: 100 },
        { duration: '30s', target: 0 },
      ],
      gracefulRampDown: '30s',
      tags: { workload: 'public' },
    },
    api_reads: {
      executor: 'ramping-vus',
      exec: 'apiReads',
      startVUs: 0,
      stages: [
        { duration: '3m', target: 40 },
        { duration: '10m', target: 40 },
        { duration: '30s', target: 0 },
      ],
      gracefulRampDown: '30s',
      tags: { workload: 'api' },
    },
  },
  thresholds: {
    http_req_failed: ['rate<0.005'],
    'http_req_duration{workload:public}': ['p(95)<300'],
    'http_req_duration{workload:api}': ['p(95)<300'],
  },
};

export function setup() {
  const response = http.post(
    `${BASE}/api/v1/auth/login`,
    JSON.stringify({ username: API_USERNAME, password: API_PASSWORD }),
    { headers: { 'Content-Type': 'application/json' } },
  );
  check(response, { 'setup: API login succeeds': (r) => r.status === 200 });
  if (response.status !== 200) {
    fail(`API login failed with HTTP ${response.status}: ${response.body}`);
  }
  return { token: response.json('token') };
}

export function publicBrowse() {
  for (const path of PUBLIC_PATHS) {
    const response = http.get(`${BASE}${path}`);
    check(response, { [`public ${path} 200`]: (r) => r.status === 200 });
    sleep(0.5 + Math.random());
  }
}

export function apiReads(data) {
  const headers = { Authorization: `Token ${data.token}` };
  for (const path of API_PATHS) {
    const response = http.get(`${BASE}${path}`, { headers });
    check(response, { [`api ${path} 200`]: (r) => r.status === 200 });
    sleep(0.2 + Math.random() * 0.5);
  }
}
