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
not `development`, `local`, or `test` unless production demo seeding is
explicitly enabled, the CLI acknowledgement is present, and the target database
name is exactly `snapstream_demo`.

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

## Zero-cost portfolio demo

**Live demo: [wajeeh-alam.github.io/snapstream](https://wajeeh-alam.github.io/snapstream/)**

The `portfolio-demo` branch contains a GitHub Pages deployment of the existing
frontend. It uses deterministic fictional data and a small browser-only API
adapter, so recent and trending feeds, text posts, likes, follows, and the demo
session remain clickable without a database, cache, object store, API keys, or
paid resources. State stays in the visitor's browser and can be reset from the
account control. It is a product walkthrough, not a production backend or a
shared multi-user service.

Live demo limitations:

- Authentication is a local demo session, not a real account system.
- Posts, likes, and follows are stored in `localStorage`, are visible only to
  that visitor, and can be cleared by the browser.
- Sample media is bundled artwork. Uploads are disabled because persistent
  private uploads require an external object store with ongoing cost.
- The static site has no live PostgreSQL or Redis service, so cache failure
  cannot be demonstrated on GitHub Pages. The repository's automated tests and
  local benchmark exercise the API's PostgreSQL fallback when Redis is down.

The public Portfolio, GitHub, X, and LinkedIn buttons are configured in
[`demo/demo-config.js`](demo/demo-config.js). Never put tokens, passwords,
private profile data, or analytics secrets in that file.

GitHub Pages is free for this public repository and is intended for static
personal project showcases. The deployment publishes only the generated static
artifact; it does not copy `.env`, server code, or local data. A production
deployment of the FastAPI/PostgreSQL/Redis/S3 architecture is available on
request, but is intentionally not kept running because it would incur ongoing
infrastructure costs.

Build the exact Pages artifact locally with:

```sh
./scripts/build_static_demo.sh
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

## Hosted demo status

The zero-cost static demo is live on GitHub Pages at
[wajeeh-alam.github.io/snapstream](https://wajeeh-alam.github.io/snapstream/).
It publishes only fictional sample data and browser-local interactions; no
secrets, private data, database, cache, or object storage are deployed.

The production backend has intentionally not been provisioned. The durable
Render configuration in `render.yaml` would create paid resources, so it remains
an opt-in deployment path rather than part of the public portfolio demo.

The Blueprint keeps `APP_ENV=production`, runs Alembic before each release, and
seeds only once through Render's initial deploy hook. Production seeding needs
`DEMO_SEED_ENABLED=true`, `--allow-production-demo`, and a database named exactly
`snapstream_demo`. The database is separate from any real application data,
contains fictional accounts only, and public self-registration is disabled.

Limitations of a future shared backend demo:

- The shared `maya_frames` account can like, follow, and create text posts, so
  visitors can change the common demo state.
- Uploads are disabled until a separate S3-compatible object store is approved
  and configured. Keeping the service stateless is preferable to storing uploads
  on one web instance's disk.
- Render's free Key Value instance is an in-memory cache. A cache restart signs
  users out, while public feeds continue through the PostgreSQL fallback.
- The smallest always-on web service and paid PostgreSQL instance were about
  $13 USD/month combined as of 2026-10-29, before bandwidth or storage growth.
  Render documents a [$7 web plan](https://render.com/pricing), paid PostgreSQL
  starting at [$6/month](https://render.com/articles/managed-postgresql-pricing-2026),
  and estimates the same [$13/month combination](https://render.com/articles/how-much-does-cloud-application-hosting-cost-for-small-businesses).
  The free PostgreSQL alternative [expires after 30 days and has no backups](https://render.com/docs/free),
  so it does not meet this demo's persistence requirement.

Deployment requires accepting Render's [Terms of Service](https://render.com/terms)
and [Acceptable Use Policy](https://render.com/acceptable-use). No account,
payment method, paid resource, or AWS resource has been created as part of this
preparation.

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
