# SnapStream

SnapStream is a production-oriented social feed demo built to show the complete
path from local containers to a horizontally scaled ECS deployment. It includes
a responsive browser client, fictional seed content, social interactions,
private media uploads, and a resilient cached API.

## Architecture

- FastAPI serves the zero-build frontend plus authentication, upload signing,
  post creation, likes, follows, and recent or trending feeds.
- PostgreSQL stores users, posts, likes, follows, and private S3 object metadata.
  Media bytes never pass through the API or its container filesystem.
- Redis stores opaque user sessions and short-lived feed responses. Creating a
  post advances a cache generation so stale feeds are no longer read.
- Browsers upload directly to a private S3 bucket with a short-lived presigned
  `PUT`; the API verifies object ownership, content type, and size with S3
  before attaching it to a post.
- ECS Fargate runs multiple stateless API tasks behind an Application Load
  Balancer. RDS PostgreSQL and ElastiCache Valkey remain in private subnets.

## Run locally

Requirements are Python 3.12-3.14, `uv`, and Docker with Compose.

```sh
cp .env.example .env
uv sync --extra test
./scripts/dev.sh --profile localstack
```

In another terminal, apply the schema and check readiness:

```sh
./scripts/compose.sh exec api alembic upgrade head
curl "http://127.0.0.1:${CONDUCTOR_PORT:-8000}/health/ready"
```

### Explore the browser demo

With the stack running, seed 8 fictional creators, 24 posts, social interactions,
and generated image assets. The password is read from your shell and is never
stored in the repository:

```sh
read -s DEMO_PASSWORD && export DEMO_PASSWORD
./scripts/seed_demo.sh --reset
```

Open `http://127.0.0.1:${CONDUCTOR_PORT:-8000}/` and sign in as
`maya_frames` with the password you entered. You can switch between recent and
trending feeds, like posts, follow creators, upload media, and publish a post.
The seed command is deterministic and safe to rerun; `--reset` replaces only its
known demo users and their related records. It refuses to run when `APP_ENV` is
not `development`, `local`, or `test`.

To test the implementation without using AWS credits:

```sh
uv run pytest -q
curl "http://127.0.0.1:${CONDUCTOR_PORT:-8000}/health/ready"
curl "http://127.0.0.1:${CONDUCTOR_PORT:-8000}/feed?kind=trending&limit=5"
```

The optional LocalStack container emulates S3 locally. Running this workflow
does not create chargeable AWS resources.

Without Docker, the application test suite is infrastructure-free:

```sh
uv sync --extra test
uv run pytest -q
```

## Reproducible feed benchmark

With the Docker stack running, measure both the Redis-cached feed and the
PostgreSQL fallback path:

```sh
PATH="/Applications/Docker.app/Contents/Resources/bin:$PATH" \
  ./scripts/benchmark_feed.sh
```

The script seeds 100 posts, sends 1,000 feed requests at concurrency 20,
reports throughput plus mean/p50/p95/p99/max latency, stops Redis, repeats the
same workload against the database fallback, and restores Redis even if the
benchmark fails. Override the workload with `BENCHMARK_REQUESTS`,
`BENCHMARK_CONCURRENCY`, and `BENCHMARK_SEED_POSTS`. Results describe one local
machine and should not be presented as production capacity; keep the workload,
hardware, and environment alongside any published numbers.

On the recorded three-trial Apple M5/Docker baseline, the Redis-cached path
delivered 6.7x the median throughput (2,219.1 versus 330.7 req/s) and 85% lower
median p50 latency (8.50 versus 57.96 ms) than the Redis-unavailable fallback.
After Redis was deliberately stopped, all 3,000 sampled fallback requests still
returned HTTP 200. These are local comparative results, not production capacity
measurements.

See [`docs/feed-benchmark.md`](docs/feed-benchmark.md) for the recorded local
baseline, exact environment, limitations, and comparison methodology.

Stop the local stack with `./scripts/stop.sh`. Compose uses a distinct project
name and host port for each Conductor workspace.

## API flow

1. `POST /auth/register` or `POST /auth/login` returns an opaque bearer token.
2. `POST /uploads/presign` returns a private S3 upload URL and required headers.
3. Upload the media bytes directly to that URL with `PUT`.
4. `POST /posts` with the returned object key creates the post after S3
   verification.
5. `GET /feed?kind=recent` or `GET /feed?kind=trending` reads the Redis-cached
   feed, falling back to PostgreSQL when the cache is unavailable.
6. `POST`/`DELETE /posts/{post_id}/likes` and
   `POST`/`DELETE /users/{user_id}/follow` provide idempotent social actions.
7. `GET /posts/{post_id}/media-url` creates a short-lived view URL for private
   media without making the S3 bucket public.

Interactive API documentation is available at `/docs` while the service runs.
Liveness is `/health/live`; dependency readiness is `/health/ready`.

## Deploy to AWS

The Terraform stack lives in [`infra/`](infra/README.md). Its runbook covers
initial ECR creation, image build and push, full infrastructure deployment,
one-off Alembic migrations on Fargate, TLS, secrets, and later releases.

Terraform provisions:

- a two-AZ VPC with public ALB/NAT and private application/data subnets;
- ECR, ECS Fargate, ALB, CloudWatch logs, and CPU/memory autoscaling;
- encrypted Multi-AZ RDS PostgreSQL and authenticated TLS ElastiCache Valkey;
- a private, encrypted, versioned S3 upload bucket with explicit-origin CORS;
- scoped task/execution IAM roles and Secrets Manager connection URLs.

Production credentials are generated by Terraform unless supplied securely.
They remain sensitive in Terraform state, so use an encrypted remote backend
with locking rather than committing or retaining local production state.
