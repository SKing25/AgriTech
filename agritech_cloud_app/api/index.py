"""Vercel Serverless Function Entrypoint para AgriTech Precision."""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Agregar el directorio base de agritech_cloud_app a sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

os.environ.setdefault("VERCEL", "1")

from app import create_app  # noqa: E402

# Objeto WSGI exportado requerido por @vercel/python
app = create_app()
