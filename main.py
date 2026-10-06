"""Uvicorn entrypoint: allows `uvicorn main:app` from the backend folder."""

from app.main import app

__all__ = ["app"]
