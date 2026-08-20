"""Vercel serverless entry point.

Adds the project root to sys.path so that ``from src.api.main import app``
works regardless of where Vercel runs the function from.
"""

import sys
import os

# Make the project root importable (parent of the ``api/`` directory).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.api.main import app  # noqa: E402  (import after sys.path patch)

__all__ = ["app"]