#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo_dir="$(cd -- "${script_dir}/.." && pwd)"
base_url="${BENCHMARK_BASE_URL:-http://127.0.0.1:${CONDUCTOR_PORT:-8000}}"
requests="${BENCHMARK_REQUESTS:-1000}"
concurrency="${BENCHMARK_CONCURRENCY:-20}"
seed_posts="${BENCHMARK_SEED_POSTS:-100}"

cd "${repo_dir}"

if ! curl --fail --silent --show-error "${base_url}/health/ready" >/dev/null; then
  echo "SnapStream is not ready at ${base_url}; start the Docker stack first." >&2
  exit 1
fi

redis_was_stopped=false
restore_redis() {
  if [[ "${redis_was_stopped}" == "true" ]]; then
    "${script_dir}/compose.sh" start redis >/dev/null
  fi
}
trap restore_redis EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

echo "Seeding ${seed_posts} posts and measuring the Redis-cached feed..." >&2
python3 "${script_dir}/benchmark_feed.py" \
  --base-url "${base_url}" \
  --seed-posts "${seed_posts}" \
  --requests "${requests}" \
  --concurrency "${concurrency}" \
  --label redis-cached

echo "Stopping Redis to exercise the PostgreSQL fallback..." >&2
redis_was_stopped=true
"${script_dir}/compose.sh" stop redis >/dev/null
python3 "${script_dir}/benchmark_feed.py" \
  --base-url "${base_url}" \
  --requests "${requests}" \
  --concurrency "${concurrency}" \
  --label redis-unavailable-postgres-fallback

restore_redis
redis_was_stopped=false
echo "Redis restored. Readiness may take a few seconds to become healthy." >&2
