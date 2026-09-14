# Feed benchmark

This benchmark compares the Redis-cached feed path with the PostgreSQL fallback
used when Redis is unavailable, and checks that feed reads continue to succeed.

## Baseline recorded 2026-09-13

The workload used 100 seeded posts, 1,000 requests per trial, 20 concurrent
persistent HTTP connections, and three trials against one Uvicorn worker. The
API, PostgreSQL 17, and Redis 7 each ran in Docker Desktop on an Apple M5 Mac
with 16 GB host RAM; Docker had 10 CPUs and 8 GB RAM available.

| Path | Successful requests | Median throughput | Median p50 | Median p95 | Median p99 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Redis-cached | 3,000 / 3,000 | 2,219.1 req/s | 8.50 ms | 11.42 ms | 15.21 ms |
| Redis stopped; PostgreSQL fallback | 3,000 / 3,000 | 330.7 req/s | 57.96 ms | 76.07 ms | 109.25 ms |

Across these local trials, the Redis-cached path delivered 6.7 times the median
throughput and an 85% lower median p50 latency than the Redis-unavailable
fallback path. More importantly, deliberately stopping Redis still returned
HTTP 200 for all 3,000 fallback requests. These figures are a repeatable local
baseline, not an AWS capacity claim: network latency, task count, database
sizing, connection pooling, and data volume will change them.

## Reproduce it

Start the stack and apply its migration, then run:

```sh
PATH="/Applications/Docker.app/Contents/Resources/bin:$PATH" \
  ./scripts/benchmark_feed.sh
```

The script warms the feed cache before sampling, measures full HTTP response
latency, stops the Redis container, repeats the same workload, and restores
Redis through an exit trap. It emits one JSON document per measured path so
results can be captured and compared. Environment variables can change the
workload:

```sh
BENCHMARK_REQUESTS=5000 \
BENCHMARK_CONCURRENCY=50 \
BENCHMARK_SEED_POSTS=500 \
  ./scripts/benchmark_feed.sh
```

For comparable runs, report the machine, Docker allocation, API worker count,
seeded post count, request count, concurrency, and number of trials. The first
trial can include host and container warm-up effects, so use multiple trials
and report the median rather than only the fastest run.
