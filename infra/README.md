# SnapStream AWS infrastructure

This Terraform stack provisions SnapStream's production runtime in two availability zones:

- public subnets containing an internet-facing Application Load Balancer and one NAT gateway per AZ;
- private subnets containing the ECS Fargate tasks, an encrypted Multi-AZ PostgreSQL RDS instance, and a two-node encrypted Valkey replication group;
- a private, versioned, encrypted S3 upload bucket with public access blocked and browser `PUT` CORS;
- an immutable, scan-on-push ECR repository, CloudWatch application logs, least-privilege task roles, and CPU/memory ECS autoscaling.

The private subnets intentionally share one subnet per AZ across ECS, RDS, and ElastiCache. Security groups isolate the three tiers: only the ALB can reach the app, and only app tasks can reach PostgreSQL and Valkey.

## Prerequisites

- Terraform 1.6 or newer
- AWS CLI v2 and `jq`
- AWS credentials with permission to create the resources in this stack
- Docker with Buildx
- an AWS account whose selected region has at least two availability zones

Copy the non-secret example and replace its placeholder values:

```sh
cd infra
cp terraform.tfvars.example terraform.tfvars
terraform init
terraform plan -out=snapstream.tfplan
```

`terraform.tfvars` and local state/plan files are ignored in `infra/.gitignore`.

For production, configure an encrypted remote S3 backend with state locking according to your organization's account bootstrap process. Do not keep production state on a laptop: generated database and Valkey credentials are sensitive values stored in Terraform state even though CLI output redacts them.

## First image push and deployment

The ECS service cannot become healthy until its configured immutable image tag exists. For a brand-new environment, create ECR first, push the image, and then apply the complete stack. Run these commands from the repository root after setting the same region and tag used in `infra/terraform.tfvars`:

```sh
terraform -chdir=infra apply -target=aws_ecr_repository.app

AWS_REGION=us-east-1
IMAGE_TAG=release-2026-09-13.1
ECR_REPOSITORY_URL="$(terraform -chdir=infra output -raw ecr_repository_url)"

aws ecr get-login-password --region "$AWS_REGION" \
  | docker login --username AWS --password-stdin "${ECR_REPOSITORY_URL%%/*}"
docker buildx build \
  --platform linux/amd64 \
  --tag "$ECR_REPOSITORY_URL:$IMAGE_TAG" \
  --push .

terraform -chdir=infra plan -out=snapstream.tfplan
terraform -chdir=infra apply snapstream.tfplan
```

Apply the database migration as a one-off Fargate task after the first deploy
and whenever a release includes new migrations. The task runs in the same
private subnets and security group as the service:

```sh
CLUSTER="$(terraform -chdir=infra output -raw ecs_cluster_name)"
TASK_DEFINITION="$(terraform -chdir=infra output -raw ecs_task_definition_arn)"
SUBNETS="$(terraform -chdir=infra output -json private_subnet_ids | jq -r 'join(",")')"
SECURITY_GROUP="$(terraform -chdir=infra output -raw ecs_security_group_id)"

MIGRATION_TASK="$(aws ecs run-task \
  --cluster "$CLUSTER" \
  --task-definition "$TASK_DEFINITION" \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[$SUBNETS],securityGroups=[$SECURITY_GROUP],assignPublicIp=DISABLED}" \
  --overrides '{"containerOverrides":[{"name":"app","command":["alembic","upgrade","head"]}]}' \
  --query 'tasks[0].taskArn' \
  --output text)"

aws ecs wait tasks-stopped --cluster "$CLUSTER" --tasks "$MIGRATION_TASK"
test "$(aws ecs describe-tasks \
  --cluster "$CLUSTER" \
  --tasks "$MIGRATION_TASK" \
  --query 'tasks[0].containers[0].exitCode' \
  --output text)" = "0"
```

Wait for that task to stop and confirm its container exit code is zero before
directing production traffic to a schema-dependent release.

For later releases, build and push a new immutable tag, change `container_image_tag`, review the plan, and apply. The ECS deployment circuit breaker rolls back a failed deployment. The stack's default database and ALB deletion protection deliberately make an accidental full destroy fail; disable those controls only as part of an intentional teardown.

## Application environment contract

The task definition supplies these plain environment values:

- `AWS_REGION`
- `APP_ENV`
- `S3_BUCKET`
- `FEED_CACHE_TTL_SECONDS`
- `SESSION_TTL_SECONDS`
- `MAX_UPLOAD_BYTES`
- `S3_ENDPOINT_URL` only when the optional Terraform variable is non-null

It injects `DATABASE_URL` and `REDIS_URL` from two dedicated Secrets Manager secrets. The generated URLs require TLS and use `postgresql+asyncpg://` and `rediss://`, respectively. The ECS execution role can read only those two secrets; the application task role cannot read them from Secrets Manager.

By default, Terraform generates strong alphanumeric database and Valkey credentials. You can supply `database_password` and `redis_auth_token` through `TF_VAR_database_password` and `TF_VAR_redis_auth_token`, but never place either in a committed `.tfvars` file or a command line retained in shell history. Use an encrypted, tightly permissioned remote state backend because secret values necessarily exist in state. Optional customer-managed KMS keys can be set independently for RDS, ElastiCache, CloudWatch logs, and Secrets Manager; the upload bucket uses S3-managed AES-256 encryption to match the application's signed-upload contract.

Secret version IDs are recorded as non-secret task-definition labels. Credential rotation therefore creates a new task-definition revision and ECS deployment so replacement tasks receive the new values; ECS resolves injected secrets only when a task starts.

Upload expiration is disabled by default because expiring S3 objects without
also repairing PostgreSQL post metadata creates broken media references. Set
`upload_lifecycle_days` only when the product has a matching retention policy.

## TLS and DNS

With `acm_certificate_arn = null`, the ALB exposes HTTP for initial validation. For production traffic, issue or import an ACM certificate in the deployment region, set its ARN, and point your DNS record at the `alb_dns_name` output. Terraform then redirects HTTP to HTTPS and forwards TLS traffic to the target group.

Useful outputs:

```sh
terraform -chdir=infra output alb_dns_name
terraform -chdir=infra output ecs_cluster_name
terraform -chdir=infra output ecs_service_name
terraform -chdir=infra output upload_bucket_name
```
