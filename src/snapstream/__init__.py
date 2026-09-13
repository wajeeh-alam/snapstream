"""Snapstream application package."""

from .app import create_app


def main() -> None:
    """Run the API with uvicorn when invoked as a console script."""
    import uvicorn

    uvicorn.run("snapstream.app:app", host="0.0.0.0", port=8000)


__all__ = ["create_app", "main"]
