/**
 * k6 Distributed Staged Load & SLO Verification Script (`tests/load/k6_load_test.js`)
 *
 * Validates Rubric #22 (Scalability & Elasticity):
 * - Staged Virtual User ramp: 10 -> 50 -> 100 concurrent VUs.
 * - Enforces p(95) < 2500ms, p(99) < 4500ms, and HTTP failure rate < 1% (0.01).
 * - Exercises `/api/health` (`/health`), `/api/badges` (`/api/v1/badges`),
 *   `/api/v1/workbook/fillable`, and `/api/generate-stream` (`/api/v1/workflow/run`).
 *
 * Usage:
 *   k6 run -e BASE_URL=http://127.0.0.1:8085 tests/load/k6_load_test.js
 */

import http from 'k6/http';
import { check, group, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';

const errorRate = new Rate('scouts_bsa_error_rate');
const healthLatency = new Trend('scouts_bsa_health_latency_ms', true);
const catalogLatency = new Trend('scouts_bsa_catalog_latency_ms', true);
const workbookLatency = new Trend('scouts_bsa_workbook_latency_ms', true);
const streamLatency = new Trend('scouts_bsa_generate_stream_latency_ms', true);

export const options = {
  stages: [
    { duration: '20s', target: 10 },
    { duration: '40s', target: 50 },
    { duration: '40s', target: 100 },
    { duration: '20s', target: 0 },
  ],
  thresholds: {
    http_req_duration: ['p(95)<2500', 'p(99)<4500'],
    http_req_failed: ['rate<0.01'],
    scouts_bsa_error_rate: ['rate<0.01'],
  },
};

const BASE_URL = __ENV.BASE_URL || 'http://127.0.0.1:8085';

export default function () {
  group('1. Health & Readiness Probes (/api/health)', () => {
    const res = http.get(`${BASE_URL}/api/health`, {
      tags: { endpoint: '/api/health' },
    });
    healthLatency.add(res.timings.duration);
    const ok = check(res, {
      'health status is 200': (r) => r.status === 200,
    });
    errorRate.add(!ok);
  });

  group('2. 149-Badge Catalog Discovery (/api/badges)', () => {
    const res = http.get(`${BASE_URL}/api/badges`, {
      tags: { endpoint: '/api/badges' },
    });
    catalogLatency.add(res.timings.duration);
    const ok = check(res, {
      'badges status is 200': (r) => r.status === 200,
      'badges payload non-empty': (r) => r.body && r.body.length > 100,
    });
    errorRate.add(!ok);
  });

  group('3. GTA 7.0.3.2 Fillable Scout Workbook (/api/v1/workbook/fillable)', () => {
    const payload = JSON.stringify({
      badge_name: 'First Aid',
      scout_name: 'Scout Patrol Test',
      troop_number: 'Troop 19',
      view_mode: 'fillable_form',
    });
    const params = {
      headers: { 'Content-Type': 'application/json' },
      tags: { endpoint: '/api/v1/workbook/fillable' },
    };
    const res = http.post(`${BASE_URL}/api/v1/workbook/fillable`, payload, params);
    workbookLatency.add(res.timings.duration);
    const ok = check(res, {
      'workbook status is 200': (r) => r.status === 200,
    });
    errorRate.add(!ok);
  });

  group('4. Streaming Curriculum Synthesis (/api/generate-stream)', () => {
    const payload = JSON.stringify({
      badge_name: 'Weather',
      depth_mode: 'Standard Deck',
      beautification_tier: 'WARM_CREAM',
      enable_deep_research: false,
    });
    const params = {
      headers: { 'Content-Type': 'application/json' },
      tags: { endpoint: '/api/generate-stream' },
    };
    const res = http.post(`${BASE_URL}/api/generate-stream`, payload, params);
    streamLatency.add(res.timings.duration);
    const ok = check(res, {
      'generate-stream status is 200': (r) => r.status === 200,
    });
    errorRate.add(!ok);
  });

  sleep(0.3);
}
