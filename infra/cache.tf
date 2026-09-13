resource "random_password" "redis" {
  count = var.redis_auth_token == null ? 1 : 0

  length  = 40
  special = false
}

resource "aws_elasticache_replication_group" "redis" {
  replication_group_id = local.replication_group_id
  description          = "SnapStream ${var.environment} cache and session store"

  engine         = "valkey"
  engine_version = var.redis_engine_version
  node_type      = var.redis_node_type
  port           = 6379

  num_cache_clusters         = 2
  automatic_failover_enabled = true
  multi_az_enabled           = true

  subnet_group_name  = aws_elasticache_subnet_group.this.name
  security_group_ids = [aws_security_group.redis.id]

  at_rest_encryption_enabled = true
  kms_key_id                 = var.redis_kms_key_arn
  transit_encryption_enabled = true
  auth_token                 = local.redis_auth_token
  auth_token_update_strategy = "SET"

  snapshot_retention_limit = var.redis_snapshot_retention_limit
  snapshot_window          = "05:30-06:30"
  maintenance_window       = "sun:07:00-sun:08:00"
  apply_immediately        = false

  tags = { Name = "${local.name}-valkey" }
}

resource "aws_secretsmanager_secret" "redis_url" {
  name                    = "${local.name}/REDIS_URL"
  description             = "SnapStream application TLS Valkey connection URL"
  kms_key_id              = var.secrets_kms_key_arn
  recovery_window_in_days = 7
}

resource "aws_secretsmanager_secret_version" "redis_url" {
  secret_id = aws_secretsmanager_secret.redis_url.id
  secret_string = format(
    "rediss://default:%s@%s:%d/0",
    local.redis_auth_token,
    aws_elasticache_replication_group.redis.primary_endpoint_address,
    aws_elasticache_replication_group.redis.port,
  )
}
