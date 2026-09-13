#!/usr/bin/env bash
set -euo pipefail

bucket="${S3_BUCKET:-snapstream-local}"
region="${AWS_DEFAULT_REGION:-us-east-1}"

if ! awslocal s3api head-bucket --bucket "${bucket}" >/dev/null 2>&1; then
  if [[ "${region}" == "us-east-1" ]]; then
    awslocal s3api create-bucket --bucket "${bucket}"
  else
    awslocal s3api create-bucket \
      --bucket "${bucket}" \
      --create-bucket-configuration "LocationConstraint=${region}"
  fi
fi

awslocal s3api put-bucket-cors \
  --bucket "${bucket}" \
  --cors-configuration '{"CORSRules":[{"AllowedHeaders":["*"],"AllowedMethods":["PUT"],"AllowedOrigins":["*"],"ExposeHeaders":["ETag"],"MaxAgeSeconds":3600}]}'
