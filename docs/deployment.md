# Deployment Guide

## Docker Compose
For local development and testing, use the provided `docker-compose.yml` to spin up the database, cache, object storage, backend, and frontend.

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

## CI/CD Pipeline
GitHub Actions builds and tests all commits to `main`.
