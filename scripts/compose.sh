#!/usr/bin/env bash
set -euo pipefail

# Run Compose from the repository even when Conductor invokes this script from
# another directory. Per-workspace project names isolate containers, networks,
# and volumes while CONDUCTOR_PORT isolates host port bindings.
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo_dir="$(cd -- "${script_dir}/.." && pwd)"
cd "${repo_dir}"

workspace_key="${CONDUCTOR_WORKSPACE_ID:-${CONDUCTOR_WORKSPACE_NAME:-$(basename "${repo_dir}")}}"
workspace_key="$(printf '%s' "${workspace_key}" | tr '[:upper:]' '[:lower:]' | tr -cs '[:alnum:]_-' '-' | sed 's/^-//; s/-$//')"
workspace_key="${workspace_key:-local}"
export COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-snapstream-${workspace_key}}"

if [[ -n "${CONDUCTOR_PORT:-}" ]]; then
  if [[ ! "${CONDUCTOR_PORT}" =~ ^[0-9]+$ ]] || (( CONDUCTOR_PORT < 1 || CONDUCTOR_PORT > 65534 )); then
    echo "CONDUCTOR_PORT must be an integer between 1 and 65534" >&2
    exit 64
  fi
  export LOCALSTACK_HOST_PORT="${LOCALSTACK_HOST_PORT:-$((CONDUCTOR_PORT + 1))}"
fi

# A profile-enabled stack gets self-contained LocalStack defaults. Explicit
# shell or .env values still take precedence.
localstack_enabled=false
case ",${COMPOSE_PROFILES:-}," in
  *,localstack,*) localstack_enabled=true ;;
esac
previous=""
for argument in "$@"; do
  if [[ "${previous}" == "--profile" && "${argument}" == "localstack" ]]; then
    localstack_enabled=true
  fi
  if [[ "${argument}" == "--profile=localstack" ]]; then
    localstack_enabled=true
  fi
  previous="${argument}"
done

if [[ "${localstack_enabled}" == "true" ]]; then
  export S3_BUCKET="${S3_BUCKET:-snapstream-local}"
  export S3_REGION="${S3_REGION:-us-east-1}"
  export S3_ENDPOINT_URL="${S3_ENDPOINT_URL:-http://localstack:4566}"
  export S3_PRESIGN_ENDPOINT_URL="${S3_PRESIGN_ENDPOINT_URL:-http://localhost:${LOCALSTACK_HOST_PORT:-4566}}"
  export AWS_ACCESS_KEY_ID="${AWS_ACCESS_KEY_ID:-test}"
  export AWS_SECRET_ACCESS_KEY="${AWS_SECRET_ACCESS_KEY:-test}"
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "docker is required; install Docker Desktop or another Docker Engine" >&2
  exit 127
fi

exec docker compose "$@"
