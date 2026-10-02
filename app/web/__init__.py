"""Web dashboard package (Flask, read-only view over the SQLite store)."""
from .server import create_app

__all__ = ["create_app"]
