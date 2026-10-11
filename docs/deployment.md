# Deployment Guide

## Docker Compose

`docker-compose.yml` is a local integration environment, not a public-internet production deployment. Copy `.env.example` to `.env`, replace every placeholder with unique local credentials, then run `docker compose up --build`. Never commit `.env`.

The backend image includes both `backend/` and the shared `ml/` package so the CV pre-processing service can start inside the container. The service refuses to start in `APP_ENV=production` if `DEBUG=true`, the JWT secret is weak/default, or CORS permits a wildcard.

## Cloud Deployment
- Backend: Containerized on AWS ECS / GCP Cloud Run
- Database: Managed PostgreSQL (RDS/Cloud SQL)
- Storage: S3 / GCS
- Frontend: Vercel / Netlify

## Edge Deployment
For rural or offline usage:
- Hardware: Raspberry Pi 4
- Runtime: ONNX Runtime for CPU-optimized inference
- Architecture: Offline-first with local SQLite and sync when online

## Release checklist

Before a production deployment, complete all of the following:

- Deploy TLS at the ingress and set HTTPS-only cookie/security policies as applicable.
- Use a managed PostgreSQL database and S3-compatible storage with private network access, backups, encryption, and least-privilege credentials.
- Do not publish PostgreSQL, Redis, or MinIO ports. Replace development MinIO credentials with a managed object-storage identity.
- Configure an explicit `CORS_ORIGINS` allow-list, a unique 32+ character `JWT_SECRET`, and secret management outside the repository.
- Implement and independently test authentication, tenant/farm authorization, rate limiting, audit retention, and object-storage access controls before exposing user data.
- Run database migrations, smoke tests, vulnerability scanning, monitoring/alerts, and restore drills.
- Keep freshness output disabled until the model-validation release gate in `docs/research.md` is satisfied.

## CI/CD Pipeline

GitHub Actions type-checks/builds the frontend, checks backend style/tests, and builds container images on pull requests and `main`.
