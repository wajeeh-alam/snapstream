output "alb_dns_name" {
  description = "Public DNS name of the application load balancer."
  value       = aws_lb.app.dns_name
}

output "ecr_repository_url" {
  description = "ECR repository URL used to tag and push application images."
  value       = aws_ecr_repository.app.repository_url
}

output "ecs_cluster_name" {
  description = "ECS cluster name."
  value       = aws_ecs_cluster.app.name
}

output "ecs_service_name" {
  description = "ECS service name."
  value       = aws_ecs_service.app.name
}

output "ecs_task_definition_arn" {
  description = "Task definition used for the service and one-off migrations."
  value       = aws_ecs_task_definition.app.arn
}

output "private_subnet_ids" {
  description = "Private subnet IDs used by ECS one-off tasks."
  value       = [for subnet in aws_subnet.private : subnet.id]
}

output "ecs_security_group_id" {
  description = "Security group ID used by ECS one-off tasks."
  value       = aws_security_group.ecs.id
}

output "upload_bucket_name" {
  description = "Private S3 upload bucket name."
  value       = aws_s3_bucket.uploads.id
}

output "database_endpoint" {
  description = "Private PostgreSQL endpoint (does not include credentials)."
  value       = aws_db_instance.postgres.endpoint
}

output "redis_primary_endpoint" {
  description = "Private TLS Valkey primary endpoint (does not include credentials)."
  value       = aws_elasticache_replication_group.redis.primary_endpoint_address
}

output "database_url_secret_arn" {
  description = "Secrets Manager ARN injected into ECS as DATABASE_URL."
  value       = aws_secretsmanager_secret.database_url.arn
}

output "redis_url_secret_arn" {
  description = "Secrets Manager ARN injected into ECS as REDIS_URL."
  value       = aws_secretsmanager_secret.redis_url.arn
}
