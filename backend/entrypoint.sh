#!/usr/bin/env bash
# Backend container entrypoint: wait for Postgres, apply migrations, then serve.
set -euo pipefail

echo "Applying database migrations (alembic upgrade head)..."
# Alembic connects using DATABASE_URL (see alembic/env.py). Retry briefly in case
# Postgres is still finishing startup despite the compose healthcheck.
for attempt in $(seq 1 30); do
  if alembic upgrade head; then
    echo "Migrations applied."
    break
  fi
  echo "Migration attempt ${attempt} failed; retrying in 2s..."
  sleep 2
  if [ "${attempt}" -eq 30 ]; then
    echo "Could not apply migrations after 30 attempts." >&2
    exit 1
  fi
done

exec python -m uvicorn backend.main:app --host 0.0.0.0 --port "${PORT:-8001}"
