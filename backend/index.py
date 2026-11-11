"""Punto de entrada para Vercel (detecta la instancia FastAPI llamada `app`).

En Vercel cada petición HTTP es una invocación serverless: la API, el webhook de
Telegram y los workers (/api/internal/tasks/*) escalan a cero cuando no hay tráfico.
"""

from app.api.main import app

__all__ = ["app"]
