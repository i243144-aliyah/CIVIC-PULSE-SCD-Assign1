#!/usr/bin/env bash
set -Eeuo pipefail

base_url="http://localhost:8000"
COMPOSE=(docker compose -f compose.yaml)
project_suffix="${GITHUB_RUN_ID:-local}-${GITHUB_RUN_ATTEMPT:-$$}"
export COMPOSE_PROJECT_NAME="civicpulse-ci-${project_suffix}"
temp_dir=$(mktemp -d)

dump_logs() {
  local exit_code=$?
  trap - ERR

  echo "::error::Compose integration smoke test failed with exit code ${exit_code}."
  echo "::group::Compose container status"
  "${COMPOSE[@]}" ps -a || true
  echo "::endgroup::"
  echo "::group::Compose container logs"
  "${COMPOSE[@]}" logs --no-color --timestamps || true
  echo "::endgroup::"
}

wait_for_healthy() {
  local service="$1"
  local label="$2"
  local container_id status

  for attempt in {1..30}; do
    container_id=$("${COMPOSE[@]}" ps -a -q "$service")
    if [[ -n "$container_id" ]]; then
      status=$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}no-healthcheck{{end}}' "$container_id")
      if [[ "$status" == "healthy" ]]; then
        echo "${label} is healthy."
        return 0
      fi
      if [[ "$status" == "unhealthy" ]]; then
        break
      fi
    fi
    sleep 2
  done

  echo "${label} did not become healthy within 120 seconds." >&2
  return 1
}

teardown() {
  "${COMPOSE[@]}" down -v --remove-orphans || true
  rm -rf "$temp_dir"
}
trap dump_logs ERR
trap teardown EXIT

"${COMPOSE[@]}" up -d --build
wait_for_healthy database PostgreSQL
wait_for_healthy cache Redis

echo "Waiting for backend health."
backend_healthy=false
for attempt in {1..30}; do
  if curl --fail --silent --show-error --max-time 5 "${base_url}/health" >/dev/null; then
    backend_healthy=true
    break
  fi
  sleep 2
done
[[ "$backend_healthy" == true ]]

"${COMPOSE[@]}" exec -T backend alembic upgrade head

complaint_payload='{"text":"A burst water pipe is flooding the main road","location":"Civic Square"}'
complaint_status=$(curl --silent --show-error --output "${temp_dir}/complaint.json" \
  --write-out '%{http_code}' --request POST "${base_url}/api/complaints" \
  --header 'Content-Type: application/json' --data "$complaint_payload")
[[ "$complaint_status" == "201" ]]

complaint_id=$(python -c 'import json,sys; print(json.load(open(sys.argv[1]))["id"])' \
  "${temp_dir}/complaint.json")
get_status=$(curl --silent --show-error --output "${temp_dir}/complaint-get.json" \
  --write-out '%{http_code}' "${base_url}/api/complaints/${complaint_id}")
[[ "$get_status" == "200" ]]
python -c 'import json,sys; data=json.load(open(sys.argv[1])); assert data["id"] == sys.argv[2]; assert data["text"] == "A burst water pipe is flooding the main road"' \
  "${temp_dir}/complaint-get.json" "$complaint_id"

first_cache=$(curl --silent --show-error --dump-header "${temp_dir}/stats-miss.headers" \
  --output "${temp_dir}/stats-miss.json" --write-out '%{http_code}' "${base_url}/api/stats")
[[ "$first_cache" == "200" ]]
grep --quiet --ignore-case '^X-Cache: MISS' "${temp_dir}/stats-miss.headers"

second_cache=$(curl --silent --show-error --dump-header "${temp_dir}/stats-hit.headers" \
  --output "${temp_dir}/stats-hit.json" --write-out '%{http_code}' "${base_url}/api/stats")
[[ "$second_cache" == "200" ]]
grep --quiet --ignore-case '^X-Cache: HIT' "${temp_dir}/stats-hit.headers"

echo "Compose integration smoke test passed"