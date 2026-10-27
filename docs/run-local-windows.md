# Run EggVision locally on Windows

## What this launch provides

This release runs a local research MVP: controlled image upload, image-quality gating, egg contour/geometry processing, scan history, batch registration, and operational dashboard counts. It does not provide a validated freshness, age, Haugh Unit, crack, blood-spot, or food-safety prediction. The UI will report `MODEL_NOT_READY` for those outputs.

## Requirements

Install Docker Desktop for Windows and enable Linux containers. Start Docker Desktop and wait until its engine is running. You also need a modern browser. Node.js and Python are optional when you use Docker Compose.

## First run

1. Open PowerShell in the project folder.
2. Copy the configuration template:

   ```powershell
   Copy-Item .env.example .env
   ```

3. Open `.env` and replace every `replace-with-...` value with a unique password or secret. Use a randomly generated JWT secret longer than 32 characters. For the included RustFS object store, set `S3_ACCESS_KEY` to exactly the same value as `MINIO_ROOT_USER`, and `S3_SECRET_KEY` to exactly the same value as `MINIO_ROOT_PASSWORD`. With `S3_REQUIRED=false`, the local stack will still run using its mounted upload volume when object storage is unavailable; the health endpoint will intentionally show `storage: degraded` in that case.
4. Start the stack:

   ```powershell
   docker compose up --build
   ```

5. Wait for the migration message and service logs. Open `http://localhost:3000`.

The backend API documentation is available at `http://localhost:8000/docs`. Docker applies the Alembic database migration before starting the API.

## Smoke test

1. Open the Scan page.
2. Upload one JPEG, PNG, or WebP image captured in a dark candling chamber.
3. Confirm that a poor image produces a retake request or that an acceptable image appears in History.
4. Open Dashboard and confirm its captured-scan count changes.
5. Confirm the Result page shows `MODEL_NOT_READY`, not a fabricated freshness result.

## Stop or reset

Stop services with `Ctrl+C`, then run:

```powershell
docker compose down
```

For a complete local reset, first confirm that the project data can be discarded, then run `docker compose down -v`. This permanently removes local PostgreSQL, Redis, MinIO, and upload volumes.

## Development mode

With Python 3.11 and Node 20 installed, start PostgreSQL, Redis, and MinIO in Docker, then run the backend and frontend separately. Set `PYTHONPATH` to the project root and `backend` directory before running pytest or Uvicorn, because the backend imports the shared `ml` package.

## Before any public deployment

Use the production checklist in `docs/deployment.md`. Set `APP_ENV=production`, `DEBUG=false`, `AUTH_REQUIRED=true`, and `S3_REQUIRED=true`. Before exposing protected APIs, create the first administrator exactly once by calling `POST /api/v1/auth/bootstrap` with the configured `BOOTSTRAP_TOKEN`, then authenticate through `POST /api/v1/auth/login` and send the returned bearer token with every protected request. Place the frontend/API behind TLS, do not publish database/cache/object-store ports, configure secret management and backups, and keep the freshness model disabled until the validation gate in `docs/research.md` is complete.
