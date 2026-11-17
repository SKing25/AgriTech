"""Vercel Serverless Function Entrypoint (Root) para AgriTech Precision."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
APP_DIR = ROOT_DIR / "agritech_cloud_app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

os.environ.setdefault("VERCEL", "1")

from app import create_app  # noqa: E402

app = create_app()
