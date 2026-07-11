"""Vercel Python serverless entrypoint.

Vercel scans the top-level api/ directory and serves the ASGI `app` it finds
here. We just re-export the FastAPI app from backend/. The rewrite in
vercel.json sends every /api/* request to this function, and the app's routes
are already defined under /api/*, so paths line up without a prefix change.
"""

import os
import sys

# backend/ isn't a package from the repo root, so add it to the import path.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from database import init_db  # noqa: E402
from main import app  # noqa: E402

# Vercel's serverless Python runtime does not reliably fire ASGI lifespan/
# startup events, so the app's @on_event("startup") init won't run there.
# Seed the (temp) db explicitly on cold start instead. init_db() is idempotent.
init_db()

__all__ = ["app"]
