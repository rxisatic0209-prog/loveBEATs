"""Vercel entrypoint for LoveBeats.

This file imports the existing FastAPI app from backend/app/main.py.

Notes:
- This is suitable for a portfolio/demo deployment.
- SQLite and log files on Vercel serverless functions should be treated as ephemeral.
- For a real multi-user public demo, replace SQLite with an external database such as Supabase/Postgres/Neon.
"""

from pathlib import Path
import os
import sys

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"

# Let Python import `app.*` from backend/app.
sys.path.insert(0, str(BACKEND))

# Vercel functions can write safely to /tmp.
os.environ.setdefault("SQLITE_PATH", "/tmp/LoveBeats.db")
os.environ.setdefault("LOG_DIR", "/tmp/lovebeats_logs")

from app.main import app  # noqa: E402
