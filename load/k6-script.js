import http from 'k6/http'
import { check, sleep } from 'k6'

const baseURL = (__ENV.TARGET_URL || __ENV.BASE_URL || 'http://localhost:8000').replace(/\/$/, '')
const duration = __ENV.DURATION || '10m'
const jsonParams = {
  headers: { 'Content-Type': 'application/json' },
  tags: { endpoint: 'create_complaint' },
}

export const options = {
  scenarios: {
    create_complaints: {
      executor: 'constant-arrival-rate',
      rate: 1,
      timeUnit: '5s',
      duration,
      preAllocatedVUs: 2,
      maxVUs: 8,
      exec: 'createComplaint',
    },
    list_complaints: {
      executor: 'constant-arrival-rate',
      rate: 1,
      timeUnit: '1s',
      duration,
      preAllocatedVUs: 2,
      maxVUs: 8,
      exec: 'listComplaints',
    },
    read_stats: {
      executor: 'constant-arrival-rate',
      rate: 2,
      timeUnit: '1s',
      duration,
      preAllocatedVUs: 2,
      maxVUs: 8,
      exec: 'readStats',
    },
  },
  thresholds: {
    http_req_failed: ['rate<0.02'],
    http_req_duration: ['p(95)<2000'],
    checks: ['rate>0.98'],
  },
}

export function createComplaint() {
  const payload = JSON.stringify({
    text: `k6 load-test report ${__VU}-${__ITER} generated at ${Date.now()} describing a damaged public road surface`,
    location: `Load test Ward ${__VU}`,
  })
  const response = http.post(`${baseURL}/api/complaints`, payload, jsonParams)
  check(response, {
    'complaint accepted': (result) => result.status === 201,
  })
  sleep(0.1)
}

export function listComplaints() {
  const response = http.get(`${baseURL}/api/complaints?page=1&page_size=20`, {
    tags: { endpoint: 'list_complaints' },
  })
  check(response, {
    'complaint list returned': (result) => result.status === 200,
  })
  sleep(0.1)
}

export function readStats() {
  const response = http.get(`${baseURL}/api/stats`, {
    tags: { endpoint: 'stats' },
  })
  check(response, {
    'stats returned': (result) => result.status === 200,
  })
  sleep(0.1)
}