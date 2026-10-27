#!/bin/sh
set -eu

# Alembic and Uvicorn import the application from backend/app.  Render uses
# this image without the Compose-specific PYTHONPATH override, so make the
# import contract explicit here as well.
export PYTHONPATH="/app/backend:/app${PYTHONPATH:+:$PYTHONPATH}"

echo "Applying database migrations..."
alembic upgrade head

exec "$@"
