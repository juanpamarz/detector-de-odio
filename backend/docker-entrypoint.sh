#!/bin/sh
# Una imagen, varios roles. Ejemplos:
#   docker run IMAGEN api        -> FastAPI (panel + webhook)
#   docker run IMAGEN worker     -> nodo trabajador Celery
#   docker run IMAGEN gateway    -> receptor por long-polling (solo local)
#   docker run IMAGEN migrate    -> alembic upgrade head
#   docker run IMAGEN cli seed-demo
set -e

if [ "${RUN_MIGRATIONS:-0}" = "1" ]; then
  alembic upgrade head
fi

case "$1" in
  api)
    exec uvicorn app.api.main:app --host 0.0.0.0 --port "${PORT:-8000}" --proxy-headers --forwarded-allow-ips "*"
    ;;
  worker)
    exec celery -A app.workers.celery_app worker -Q moderation,interactions \
      --concurrency "${WORKER_CONCURRENCY:-4}" --loglevel "${LOG_LEVEL:-INFO}" --without-gossip --without-mingle
    ;;
  gateway)
    exec python -m app.telegram.polling
    ;;
  migrate)
    exec alembic upgrade head
    ;;
  cli)
    shift
    exec python -m app.cli "$@"
    ;;
  *)
    exec "$@"
    ;;
esac
