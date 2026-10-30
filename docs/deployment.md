# Deployment Guide

## Docker Compose

`docker-compose.yml` is a local integration environment, not a public-internet production deployment. Copy `.env.example` to `.env`, replace every placeholder with unique local credentials, then run `docker compose up --build`. Never commit `.env`.

The backend image includes both `backend/` and the shared `ml/` package so the CV pre-processing service can start inside the container. The service refuses to start in `APP_ENV=production` if `DEBUG=true`, the JWT secret is weak/default, CORS permits a wildcard, authentication is disabled, or explicitly required object storage is incomplete.

## Render + Vercel deployment

The Render service must use the repository root as its root directory.

```text
Build Command: pip install -r backend/requirements.txt
Start Command: bash scripts/start_render_backend.sh
```

The start script derives absolute paths, exports both `backend/` and the repository root on `PYTHONPATH`, applies `alembic upgrade head` from `backend/`, then starts Uvicorn on `0.0.0.0:$PORT`. A migration failure stops the deployment.

Set these Render variable names: `APP_ENV`, `DEBUG`, `DATABASE_URL`, `REDIS_URL`, `CORS_ORIGINS`, `JWT_SECRET`, `JWT_ALGORITHM`, `JWT_EXPIRY_MINUTES`, `AUTH_REQUIRED`, `BOOTSTRAP_TOKEN`, `UPLOAD_MAX_SIZE_MB`, `UPLOAD_MAX_PIXELS`, and `HEALTHCHECK_TIMEOUT_SECONDS`. Object-storage names (`S3_REQUIRED`, `S3_ENDPOINT`, `S3_BUCKET`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`) are optional unless durable artifact storage is enabled.

Set `APP_ENV=production`, `DEBUG=false`, `AUTH_REQUIRED=true`, and `CORS_ORIGINS=https://egg-vision.vercel.app`. `JWT_SECRET` and `BOOTSTRAP_TOKEN` must be unique values of at least 32 characters. Keep `DATABASE_URL` and `REDIS_URL` independent and secret.

The Vercel project root is `frontend`; run `npm ci` and `npm run build`. It needs no `NEXT_PUBLIC_API_URL`, because the production Render endpoint is compiled in as the default. That variable remains an optional override and must end with `/api/v1`.

### Migrations and storage

`001_initial_schema` creates users, farms, devices, eggs, batches, scans, predictions, sensor readings, ground truth, model versions, and audit logs. Inspect the revision with `cd backend && alembic current`; apply it with `alembic upgrade head`. Do not use `create_all`, stamp a database blindly, or recreate a production database to fix a missing table.

Local uploads are for development only. On Render, absent S3-compatible storage leaves the service operational but reports storage as `degraded`; fallback artifacts are served through the authenticated artifact route and are ephemeral. Configure S3 and set `S3_REQUIRED=true` when durable artifact retention is required.

### Non-destructive production smoke tests

```bash
curl -i https://eggvision-1.onrender.com/api/v1/health
curl -i https://eggvision-1.onrender.com/docs
curl -i -X OPTIONS https://eggvision-1.onrender.com/api/v1/scan \
  -H "Origin: https://egg-vision.vercel.app" \
  -H "Access-Control-Request-Method: POST" \
  -H "Access-Control-Request-Headers: authorization,content-type"
curl -s https://eggvision-1.onrender.com/api/v1/model/info
```

Open the deployed frontend, sign in, upload a non-sensitive test image, and verify a capture record plus an explicit `MODEL_NOT_READY` result. Health should report infrastructure independently from the unready model.

## Edge Deployment
For rural or offline usage:
- Hardware: Raspberry Pi 4
- Runtime: ONNX Runtime for CPU-optimized inference
- Architecture: Offline-first with local SQLite and sync when online

## Release checklist

Before a production deployment, complete all of the following:

- Deploy TLS at the ingress and set HTTPS-only cookie/security policies as applicable.
- Use a managed PostgreSQL database and S3-compatible storage with private network access, backups, encryption, and least-privilege credentials. Set `S3_REQUIRED=true`; the local upload-volume fallback is not a production storage solution.
- Do not publish PostgreSQL, Redis, or MinIO ports. Replace development MinIO credentials with a managed object-storage identity.
- Configure an explicit `CORS_ORIGINS` allow-list, a unique 32+ character `JWT_SECRET`, and secret management outside the repository.
- Implement and independently test authentication, tenant/farm authorization, rate limiting, audit retention, and object-storage access controls before exposing user data.
- Run database migrations, smoke tests, vulnerability scanning, monitoring/alerts, and restore drills.
- Keep freshness output disabled until the model-validation release gate in `docs/research.md` is satisfied.

## CI/CD Pipeline

GitHub Actions type-checks/builds the frontend, checks backend style/tests, and builds container images on pull requests and `main`.
