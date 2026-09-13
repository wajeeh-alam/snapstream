"""ASGI entrypoint used by Uvicorn and the container image."""

from .app import app

__all__ = ["app"]
