#!/usr/bin/env bash
# Render starts this script from the repository root. Resolve paths from this
# file instead so imports and Alembic do not depend on that working directory.
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"

if [[ ! -d "$BACKEND_DIR/app" || ! -d "$ROOT_DIR/ml" ]]; then
  echo "EggVision startup error: expected backend/app and ml directories." >&2
  exit 1
fi

export PYTHONPATH="$BACKEND_DIR:$ROOT_DIR${PYTHONPATH:+:$PYTHONPATH}"
cd "$BACKEND_DIR"

echo "Applying database migrations..."
alembic upgrade head
echo "Database migrations applied successfully. Starting API..."

exec python -m uvicorn app.main:app \
  --app-dir "$BACKEND_DIR" \
  --host 0.0.0.0 \
  --port "${PORT:-8000}"
