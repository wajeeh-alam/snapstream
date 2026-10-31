#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo_dir="$(cd -- "${script_dir}/.." && pwd)"
output_dir="${1:-${repo_dir}/.context/portfolio-site}"

mkdir -p "${output_dir}"
cp "${repo_dir}/src/snapstream/static/index.html" "${output_dir}/index.html"
cp "${repo_dir}/src/snapstream/static/styles.css" "${output_dir}/styles.css"
cp "${repo_dir}/src/snapstream/static/app.js" "${output_dir}/app.js"
cp "${repo_dir}/demo/demo-config.js" "${output_dir}/demo-config.js"
cp "${repo_dir}/demo/demo-mode.js" "${output_dir}/demo-mode.js"

perl -0pi -e 's|href="/static/styles\.css"|href="./styles.css"|g; s|<script src="/static/app\.js" defer></script>|<script src="./demo-config.js" defer></script>\n    <script src="./demo-mode.js" defer></script>\n    <script src="./app.js" defer></script>|g' "${output_dir}/index.html"

touch "${output_dir}/.nojekyll"
printf 'Built static portfolio demo in %s\n' "${output_dir}"
