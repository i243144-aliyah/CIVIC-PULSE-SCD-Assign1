#!/usr/bin/env bash
set -euo pipefail

base_url="http://localhost:8000"
compose_down() {
  docker compose down -v
}
trap compose_down EXIT

docker compose up -d --build

ready=false
for attempt in $(seq 1 30); do
  if [[ "$(curl --silent --output /dev/null --write-out '%{http_code}' "${base_url}/ready")" == "200" ]]; then
    ready=true
    break
  fi
  sleep 1
done

if [[ "$ready" != true ]]; then
  echo "Backend did not become ready after 30 attempts" >&2
  docker compose logs backend
  exit 1
fi

complaint_payload='{"text":"A burst water pipe is flooding the main road","location":"Civic Square"}'
complaint_status=$(curl --silent --output /tmp/civicpulse-complaint.json --write-out '%{http_code}' \
  --request POST "${base_url}/api/complaints" \
  --header 'Content-Type: application/json' \
  --data "$complaint_payload")
[[ "$complaint_status" == "201" ]]

list_status=$(curl --silent --output /tmp/civicpulse-complaints.json --write-out '%{http_code}' \
  "${base_url}/api/complaints")
[[ "$list_status" == "200" ]]

triage_payload='{"text":"A burst water pipe is flooding the main road","location":"Civic Square"}'
first_cache=$(curl --silent --dump-header /tmp/civicpulse-triage-miss.headers \
  --output /tmp/civicpulse-triage-miss.json --write-out '%{http_code}' \
  --request POST "${base_url}/api/triage" \
  --header 'Content-Type: application/json' \
  --data "$triage_payload")
[[ "$first_cache" == "200" ]]
grep --quiet --ignore-case '^X-Cache: MISS' /tmp/civicpulse-triage-miss.headers

second_cache=$(curl --silent --dump-header /tmp/civicpulse-triage-hit.headers \
  --output /tmp/civicpulse-triage-hit.json --write-out '%{http_code}' \
  --request POST "${base_url}/api/triage" \
  --header 'Content-Type: application/json' \
  --data "$triage_payload")
[[ "$second_cache" == "200" ]]
grep --quiet --ignore-case '^X-Cache: HIT' /tmp/civicpulse-triage-hit.headers

echo "Compose integration smoke test passed"