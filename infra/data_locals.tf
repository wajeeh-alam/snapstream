locals {
  database_password = coalesce(var.database_password, one(random_password.database[*].result))
  redis_auth_token  = coalesce(var.redis_auth_token, one(random_password.redis[*].result))

  upload_bucket_name = coalesce(
    var.upload_bucket_name,
    "${substr(local.name, 0, min(length(local.name), 35))}-${substr(sha256("${data.aws_caller_identity.current.account_id}:${var.aws_region}:${local.name}"), 0, 12)}-uploads",
  )
}
