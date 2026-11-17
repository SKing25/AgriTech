"""Punto de entrada WSGI de producción para Gunicorn / Docker / Render."""

from app import create_app

app = create_app(iniciarSimulador=True)
