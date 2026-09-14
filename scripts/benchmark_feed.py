#!/usr/bin/env python3
"""Small dependency-free HTTP load generator for SnapStream's feed endpoint."""

from __future__ import annotations

import argparse
import concurrent.futures
import http.client
import json
import math
import secrets
import statistics
import threading
import time
import uuid
from collections.abc import Sequence
from typing import Any
from urllib.parse import urlsplit


def request_json(
    method: str,
    url: str,
    *,
    body: dict[str, Any] | None = None,
    token: str | None = None,
) -> dict[str, Any]:
    target = urlsplit(url)
    connection = http.client.HTTPConnection(target.hostname, target.port, timeout=10)
    headers = {"Accept": "application/json"}
    encoded_body = None
    if body is not None:
        encoded_body = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request_target = target.path or "/"
    if target.query:
        request_target = f"{request_target}?{target.query}"
    try:
        connection.request(method, request_target, encoded_body, headers)
        response = connection.getresponse()
        payload = response.read()
    finally:
        connection.close()
    if not 200 <= response.status < 300:
        raise RuntimeError(f"{method} {target.path} returned {response.status}: {payload!r}")
    return json.loads(payload)


def seed(base_url: str, post_count: int) -> None:
    suffix = uuid.uuid4().hex[:12]
    session = request_json(
        "POST",
        f"{base_url}/auth/register",
        body={
            "email": f"benchmark-{suffix}@example.com",
            "username": f"bench_{suffix}",
            "display_name": "Feed Benchmark",
            "password": secrets.token_urlsafe(24),
        },
    )
    token = session["access_token"]
    for number in range(post_count):
        request_json(
            "POST",
            f"{base_url}/posts",
            body={"body": f"Benchmark post {number + 1} ({suffix})"},
            token=token,
        )


def percentile(values: Sequence[float], percent: float) -> float:
    """Return a linearly interpolated percentile for an already sorted sequence."""
    position = (len(values) - 1) * percent
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return values[lower]
    return values[lower] + (values[upper] - values[lower]) * (position - lower)


def worker(
    host: str,
    port: int,
    path: str,
    request_count: int,
    start: threading.Event,
) -> tuple[list[float], int]:
    connection = http.client.HTTPConnection(host, port, timeout=10)
    latencies: list[float] = []
    failures = 0
    start.wait()
    try:
        for _ in range(request_count):
            began = time.perf_counter()
            try:
                connection.request("GET", path, headers={"Accept": "application/json"})
                response = connection.getresponse()
                response.read()
                if response.status != 200:
                    failures += 1
            except (OSError, http.client.HTTPException):
                failures += 1
                connection.close()
                connection = http.client.HTTPConnection(host, port, timeout=10)
            latencies.append((time.perf_counter() - began) * 1_000)
    finally:
        connection.close()
    return latencies, failures


def benchmark(base_url: str, label: str, requests: int, concurrency: int) -> dict[str, Any]:
    target = urlsplit(f"{base_url}/feed?kind=recent&limit=20")
    if target.scheme != "http" or target.hostname is None:
        raise ValueError("--base-url must be an http:// URL")

    # Ensure application startup and any lazy connection work is outside the sample.
    request_json("GET", f"{base_url}/feed?kind=recent&limit=20")
    per_worker = [requests // concurrency] * concurrency
    for index in range(requests % concurrency):
        per_worker[index] += 1

    start = threading.Event()
    began = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [
            executor.submit(
                worker,
                target.hostname,
                target.port or 80,
                f"{target.path}?{target.query}",
                count,
                start,
            )
            for count in per_worker
            if count
        ]
        start.set()
        samples = [future.result() for future in futures]
    duration = time.perf_counter() - began
    latencies = sorted(value for values, _ in samples for value in values)
    failures = sum(value for _, value in samples)
    return {
        "label": label,
        "requests": requests,
        "concurrency": concurrency,
        "failures": failures,
        "duration_seconds": round(duration, 3),
        "requests_per_second": round(requests / duration, 1),
        "latency_ms": {
            "mean": round(statistics.fmean(latencies), 2),
            "p50": round(percentile(latencies, 0.50), 2),
            "p95": round(percentile(latencies, 0.95), 2),
            "p99": round(percentile(latencies, 0.99), 2),
            "max": round(max(latencies), 2),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--label", default="feed")
    parser.add_argument("--requests", type=int, default=1_000)
    parser.add_argument("--concurrency", type=int, default=20)
    parser.add_argument("--seed-posts", type=int, default=0)
    args = parser.parse_args()
    if args.requests < 1 or args.concurrency < 1 or args.seed_posts < 0:
        parser.error("requests/concurrency must be positive and seed-posts cannot be negative")
    args.concurrency = min(args.concurrency, args.requests)
    base_url = args.base_url.rstrip("/")
    if args.seed_posts:
        seed(base_url, args.seed_posts)
    result = benchmark(base_url, args.label, args.requests, args.concurrency)
    print(json.dumps(result, indent=2))
    if result["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
