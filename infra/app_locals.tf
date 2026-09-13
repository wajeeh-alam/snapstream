locals {
  app_environment = concat(
    [
      { name = "APP_ENV", value = var.environment },
      { name = "AWS_REGION", value = var.aws_region },
      { name = "S3_BUCKET", value = aws_s3_bucket.uploads.id },
      { name = "FEED_CACHE_TTL_SECONDS", value = tostring(var.feed_cache_ttl_seconds) },
      { name = "SESSION_TTL_SECONDS", value = tostring(var.session_ttl_seconds) },
      { name = "MAX_UPLOAD_BYTES", value = tostring(var.max_upload_bytes) },
    ],
    var.s3_endpoint_url == null ? [] : [
      { name = "S3_ENDPOINT_URL", value = var.s3_endpoint_url },
    ],
  )

  app_secrets = [
    { name = "DATABASE_URL", valueFrom = aws_secretsmanager_secret.database_url.arn },
    { name = "REDIS_URL", valueFrom = aws_secretsmanager_secret.redis_url.arn },
  ]
}
