locals {
  name = "${var.project_name}-${var.environment}"

  load_balancer_name   = substr(local.name, 0, 32)
  target_group_name    = substr("${local.name}-app", 0, 32)
  replication_group_id = substr("${local.name}-valkey", 0, 40)

  selected_azs = var.availability_zones != null ? var.availability_zones : slice(
    data.aws_availability_zones.available.names,
    0,
    2,
  )

  common_tags = merge(
    {
      Application = var.project_name
      Environment = var.environment
      ManagedBy   = "terraform"
    },
    var.additional_tags,
  )

}
