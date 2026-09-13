# syntax=docker/dockerfile:1.7

ARG PYTHON_VERSION=3.13

# Keep uv and dependency installation out of the final image. The uv release is
# pinned independently from Python so both build stages use the same interpreter.
FROM ghcr.io/astral-sh/uv:0.12.9 AS uv

FROM python:${PYTHON_VERSION}-slim-bookworm AS builder

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_INSTALLER_METADATA=1 \
    UV_PYTHON_DOWNLOADS=never

COPY --from=uv /uv /uvx /bin/

# Install third-party dependencies first so source-only changes reuse this
# layer. --no-install-project avoids installing the project before its source
# has been copied.
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src ./src
RUN uv sync --frozen --no-dev --no-editable


FROM python:${PYTHON_VERSION}-slim-bookworm AS runtime

WORKDIR /app

ENV PATH="/app/.venv/bin:${PATH}" \
    HOME=/home/app \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --create-home \
        --home-dir /home/app --shell /usr/sbin/nologin app

COPY --from=builder --chown=app:app /app/.venv /app/.venv

USER 10001:10001

EXPOSE 8000
STOPSIGNAL SIGTERM

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/live', timeout=3)"]

CMD ["uvicorn", "snapstream.main:app", "--host", "0.0.0.0", "--port", "8000"]
