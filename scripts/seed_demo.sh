#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${DEMO_PASSWORD:-}" ]]; then
  echo "Set DEMO_PASSWORD to a local-only password with at least 8 characters." >&2
  exit 64
fi

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec "${script_dir}/compose.sh" exec -T \
  -e DEMO_PASSWORD="${DEMO_PASSWORD}" \
  api python -m snapstream.seed "$@"
