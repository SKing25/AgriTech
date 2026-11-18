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


class VercelPathFixMiddleware:
    """Corrige PATH_INFO cuando Vercel reescribe el tráfico hacia la función serverless."""

    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        path_info = environ.get("PATH_INFO", "")
        # Si Vercel pasa la ruta interna de la función serverless en vez de la ruta solicitada
        if path_info in ("/api/index.py", "/api/index", "api/index.py", "/api"):
            real_path = (
                environ.get("HTTP_X_FORWARDED_URI")
                or environ.get("HTTP_X_MATCHED_PATH")
                or environ.get("REQUEST_URI")
                or "/"
            )
            if "?" in real_path:
                real_path, q = real_path.split("?", 1)
                environ["QUERY_STRING"] = q
            environ["PATH_INFO"] = real_path

        return self.wsgi_app(environ, start_response)


# Instanciar app Flask y envolver con middleware de normalización de rutas para Vercel
app = create_app()
app.wsgi_app = VercelPathFixMiddleware(app.wsgi_app)
