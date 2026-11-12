"""
Vercel Python Function entrypoint for EggVision backend.

Vercel executes this file as a Python WSGI/ASGI serverless function.
It patches sys.path so both `backend/app` and the repository-level `ml`
package are importable, then re-exports the FastAPI `app` object.
"""
import sys
import os

# ---------------------------------------------------------------------------
# Path setup — runs once per cold-start
# ---------------------------------------------------------------------------
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # repo root
_backend = os.path.join(_root, "backend")

for _p in (_backend, _root):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# ---------------------------------------------------------------------------
# Application import
# ---------------------------------------------------------------------------
from app.main import app  # noqa: E402 — must come after path setup

# Vercel looks for a top-level `app` or `handler` variable.
__all__ = ["app"]
