variable "aws_region" {
  description = "AWS region in which to deploy SnapStream."
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Short, lowercase application name used in resource names."
  type        = string
  default     = "snapstream"

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{1,24}$", var.project_name))
    error_message = "project_name must be 2-25 lowercase letters, numbers, or hyphens and start with a letter."
  }
}

variable "environment" {
  description = "Deployment environment."
  type        = string
  default     = "production"

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{1,20}$", var.environment))
    error_message = "environment must be 2-21 lowercase letters, numbers, or hyphens and start with a letter."
  }
}

variable "additional_tags" {
  description = "Additional tags applied to all supported AWS resources."
  type        = map(string)
  default     = {}
}

variable "availability_zones" {
  description = "Exactly two AZ names. Leave null to select the first two available AZs in aws_region."
  type        = list(string)
  default     = null

  validation {
    condition     = var.availability_zones == null ? true : length(var.availability_zones) == 2
    error_message = "availability_zones must contain exactly two AZs when supplied."
  }
}

variable "vpc_cidr" {
  description = "CIDR range for the VPC."
  type        = string
  default     = "10.42.0.0/16"

  validation {
    condition     = can(cidrnetmask(var.vpc_cidr))
    error_message = "vpc_cidr must be a valid IPv4 CIDR."
  }
}

variable "public_subnet_cidrs" {
  description = "One public ALB/NAT subnet CIDR per availability zone."
  type        = list(string)
  default     = ["10.42.0.0/20", "10.42.16.0/20"]

  validation {
    condition     = length(var.public_subnet_cidrs) == 2 && alltrue([for cidr in var.public_subnet_cidrs : can(cidrnetmask(cidr))])
    error_message = "public_subnet_cidrs must contain exactly two valid IPv4 CIDRs."
  }
}

variable "private_subnet_cidrs" {
  description = "One private ECS/RDS/ElastiCache subnet CIDR per availability zone."
  type        = list(string)
  default     = ["10.42.128.0/20", "10.42.144.0/20"]

  validation {
    condition     = length(var.private_subnet_cidrs) == 2 && alltrue([for cidr in var.private_subnet_cidrs : can(cidrnetmask(cidr))])
    error_message = "private_subnet_cidrs must contain exactly two valid IPv4 CIDRs."
  }
}

variable "container_image_tag" {
  description = "Immutable ECR image tag to run. Push this tag before applying the ECS service."
  type        = string

  validation {
    condition     = length(trimspace(var.container_image_tag)) > 0 && var.container_image_tag != "latest"
    error_message = "container_image_tag must be a non-empty immutable tag and cannot be latest."
  }
}

variable "container_port" {
  description = "Port the application listens on inside the container."
  type        = number
  default     = 8000

  validation {
    condition     = var.container_port >= 1 && var.container_port <= 65535
    error_message = "container_port must be between 1 and 65535."
  }
}

variable "health_check_path" {
  description = "HTTP path used by the ALB and ECS health checks."
  type        = string
  default     = "/health/live"

  validation {
    condition     = startswith(var.health_check_path, "/")
    error_message = "health_check_path must start with /."
  }
}

variable "acm_certificate_arn" {
  description = "Optional ACM certificate ARN. When set, HTTP redirects to HTTPS."
  type        = string
  default     = null
}

variable "alb_deletion_protection" {
  description = "Protect the public load balancer from accidental deletion."
  type        = bool
  default     = true
}

variable "ecs_cpu" {
  description = "Fargate task CPU units."
  type        = number
  default     = 512
}

variable "ecs_memory" {
  description = "Fargate task memory in MiB."
  type        = number
  default     = 1024
}

variable "ecs_desired_count" {
  description = "Initial number of ECS tasks."
  type        = number
  default     = 2

  validation {
    condition     = var.ecs_desired_count >= 1
    error_message = "ecs_desired_count must be at least 1."
  }
}

variable "ecs_min_capacity" {
  description = "Minimum ECS tasks managed by autoscaling."
  type        = number
  default     = 2

  validation {
    condition     = var.ecs_min_capacity >= 1
    error_message = "ecs_min_capacity must be at least 1."
  }
}

variable "ecs_max_capacity" {
  description = "Maximum ECS tasks managed by autoscaling."
  type        = number
  default     = 10

  validation {
    condition     = var.ecs_max_capacity >= 1
    error_message = "ecs_max_capacity must be at least 1."
  }
}

variable "autoscaling_cpu_target" {
  description = "Average ECS CPU percentage targeted by autoscaling."
  type        = number
  default     = 70

  validation {
    condition     = var.autoscaling_cpu_target >= 1 && var.autoscaling_cpu_target <= 100
    error_message = "autoscaling_cpu_target must be between 1 and 100."
  }
}

variable "autoscaling_memory_target" {
  description = "Average ECS memory percentage targeted by autoscaling."
  type        = number
  default     = 75

  validation {
    condition     = var.autoscaling_memory_target >= 1 && var.autoscaling_memory_target <= 100
    error_message = "autoscaling_memory_target must be between 1 and 100."
  }
}

variable "log_retention_days" {
  description = "CloudWatch application log retention period."
  type        = number
  default     = 30
}

variable "cloudwatch_kms_key_arn" {
  description = "Optional customer-managed KMS key ARN for the ECS CloudWatch log group."
  type        = string
  default     = null
}

variable "db_name" {
  description = "PostgreSQL database name."
  type        = string
  default     = "snapstream"

  validation {
    condition     = can(regex("^[A-Za-z][A-Za-z0-9_]{0,62}$", var.db_name))
    error_message = "db_name must be a valid PostgreSQL database identifier up to 63 characters."
  }
}

variable "db_username" {
  description = "PostgreSQL master username."
  type        = string
  default     = "snapstream_admin"

  validation {
    condition     = can(regex("^[A-Za-z][A-Za-z0-9_]{0,62}$", var.db_username))
    error_message = "db_username must be a URL-safe PostgreSQL identifier up to 63 characters."
  }
}

variable "database_password" {
  description = "Optional PostgreSQL password. Leave null to generate one. Never put this value in a committed tfvars file."
  type        = string
  sensitive   = true
  default     = null

  validation {
    condition     = var.database_password == null ? true : can(regex("^[A-Za-z0-9]{16,128}$", var.database_password))
    error_message = "database_password must contain 16-128 ASCII letters or numbers when supplied."
  }
}

variable "db_engine_version" {
  description = "PostgreSQL engine version."
  type        = string
  default     = "16"
}

variable "db_instance_class" {
  description = "RDS instance class."
  type        = string
  default     = "db.t4g.micro"
}

variable "db_allocated_storage" {
  description = "Initial PostgreSQL storage in GiB."
  type        = number
  default     = 20
}

variable "db_max_allocated_storage" {
  description = "Maximum autoscaled PostgreSQL storage in GiB."
  type        = number
  default     = 100
}

variable "db_multi_az" {
  description = "Enable an RDS Multi-AZ standby."
  type        = bool
  default     = true
}

variable "db_backup_retention_period" {
  description = "Automated backup retention in days."
  type        = number
  default     = 7
}

variable "db_deletion_protection" {
  description = "Protect the database from accidental deletion."
  type        = bool
  default     = true
}

variable "db_skip_final_snapshot" {
  description = "Skip the final snapshot on deletion. Keep false for production."
  type        = bool
  default     = false
}

variable "db_final_snapshot_identifier" {
  description = "Optional final snapshot name; defaults to <project>-<environment>-final."
  type        = string
  default     = null
}

variable "db_kms_key_arn" {
  description = "Optional customer-managed KMS key ARN for RDS storage."
  type        = string
  default     = null
}

variable "redis_node_type" {
  description = "ElastiCache Valkey node type."
  type        = string
  default     = "cache.t4g.micro"
}

variable "redis_engine_version" {
  description = "ElastiCache Valkey engine version."
  type        = string
  default     = "7.2"
}

variable "redis_auth_token" {
  description = "Optional Valkey AUTH token. Leave null to generate one. Never put this value in a committed tfvars file."
  type        = string
  sensitive   = true
  default     = null

  validation {
    condition     = var.redis_auth_token == null ? true : can(regex("^[A-Za-z0-9]{16,128}$", var.redis_auth_token))
    error_message = "redis_auth_token must contain 16-128 ASCII letters or numbers when supplied."
  }
}

variable "redis_kms_key_arn" {
  description = "Optional customer-managed KMS key ARN for ElastiCache at-rest encryption."
  type        = string
  default     = null
}

variable "redis_snapshot_retention_limit" {
  description = "Number of days to retain automatic Valkey snapshots."
  type        = number
  default     = 7
}

variable "secrets_kms_key_arn" {
  description = "Optional customer-managed KMS key ARN for DATABASE_URL and REDIS_URL secrets."
  type        = string
  default     = null
}

variable "feed_cache_ttl_seconds" {
  description = "FEED_CACHE_TTL_SECONDS application setting."
  type        = number
  default     = 300

  validation {
    condition     = var.feed_cache_ttl_seconds >= 1 && var.feed_cache_ttl_seconds <= 3600
    error_message = "feed_cache_ttl_seconds must be between 1 and 3600."
  }
}

variable "session_ttl_seconds" {
  description = "SESSION_TTL_SECONDS application setting."
  type        = number
  default     = 86400

  validation {
    condition     = var.session_ttl_seconds >= 60 && var.session_ttl_seconds <= 31536000
    error_message = "session_ttl_seconds must be between 60 and 31536000."
  }
}

variable "max_upload_bytes" {
  description = "MAX_UPLOAD_BYTES application setting."
  type        = number
  default     = 10485760

  validation {
    condition     = var.max_upload_bytes >= 1 && var.max_upload_bytes <= 5368709120
    error_message = "max_upload_bytes must be between 1 byte and 5 GiB."
  }
}

variable "s3_endpoint_url" {
  description = "Optional S3-compatible endpoint exposed to the application. Normally null on AWS."
  type        = string
  default     = null
}

variable "upload_bucket_name" {
  description = "Optional globally unique upload bucket name. A deterministic account/region-qualified name is used when null."
  type        = string
  default     = null

  validation {
    condition = var.upload_bucket_name == null ? true : (
      length(var.upload_bucket_name) >= 3 &&
      length(var.upload_bucket_name) <= 63 &&
      can(regex("^[a-z0-9][a-z0-9.-]*[a-z0-9]$", var.upload_bucket_name))
    )
    error_message = "upload_bucket_name must be a valid 3-63 character lowercase S3 bucket name."
  }
}

variable "upload_cors_allowed_origins" {
  description = "Exact browser origins allowed to PUT uploads directly to S3."
  type        = list(string)

  validation {
    condition     = length(var.upload_cors_allowed_origins) > 0 && !contains(var.upload_cors_allowed_origins, "*")
    error_message = "upload_cors_allowed_origins must include at least one explicit origin and cannot contain *."
  }
}

variable "upload_lifecycle_days" {
  description = "Expire current uploads after this many days; set 0 to disable."
  type        = number
  default     = 0

  validation {
    condition     = var.upload_lifecycle_days >= 0
    error_message = "upload_lifecycle_days cannot be negative."
  }
}
