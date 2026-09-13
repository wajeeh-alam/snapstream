resource "random_password" "database" {
  count = var.database_password == null ? 1 : 0

  length  = 40
  special = false
}

resource "aws_db_instance" "postgres" {
  identifier = "${local.name}-postgres"

  engine         = "postgres"
  engine_version = var.db_engine_version
  instance_class = var.db_instance_class

  db_name  = var.db_name
  username = var.db_username
  password = local.database_password
  port     = 5432

  allocated_storage     = var.db_allocated_storage
  max_allocated_storage = var.db_max_allocated_storage
  storage_type          = "gp3"
  storage_encrypted     = true
  kms_key_id            = var.db_kms_key_arn

  db_subnet_group_name   = aws_db_subnet_group.this.name
  vpc_security_group_ids = [aws_security_group.rds.id]
  publicly_accessible    = false
  multi_az               = var.db_multi_az

  backup_retention_period = var.db_backup_retention_period
  backup_window           = "03:00-04:00"
  maintenance_window      = "sun:04:30-sun:05:30"
  copy_tags_to_snapshot   = true

  auto_minor_version_upgrade = true
  deletion_protection        = var.db_deletion_protection
  skip_final_snapshot        = var.db_skip_final_snapshot
  final_snapshot_identifier  = var.db_skip_final_snapshot ? null : coalesce(var.db_final_snapshot_identifier, "${local.name}-final")

  tags = { Name = "${local.name}-postgres" }
}

resource "aws_secretsmanager_secret" "database_url" {
  name                    = "${local.name}/DATABASE_URL"
  description             = "SnapStream application PostgreSQL connection URL"
  kms_key_id              = var.secrets_kms_key_arn
  recovery_window_in_days = 7
}

resource "aws_secretsmanager_secret_version" "database_url" {
  secret_id = aws_secretsmanager_secret.database_url.id
  secret_string = format(
    "postgresql+asyncpg://%s:%s@%s:%d/%s?ssl=require",
    var.db_username,
    local.database_password,
    aws_db_instance.postgres.address,
    aws_db_instance.postgres.port,
    var.db_name,
  )
}
