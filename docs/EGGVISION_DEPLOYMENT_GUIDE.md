# EggVision AI — Production Deployment & Cloud Infrastructure Guide
**Document Version:** 1.0.0  
**Target Environments:** Vercel (Frontend), Render (Backend, PostgreSQL, Redis), Docker Compose (Local Dev)

---

## 1. Cloud Architecture & Service Mapping

```
[ User Browser ]
       │
       ├─── (HTTPS: egg-vision.vercel.app) ────► [ Vercel Edge CDN: Next.js 14 Frontend ]
       │                                                      │
       └─── (HTTPS: eggvision-1.onrender.com) ──┐             │ (Client-Side API Calls)
                                                ▼             ▼
                                [ Render Web Service: FastAPI + Uvicorn ]
                                                │
                 ┌──────────────────────────────┼──────────────────────────────┐
                 ▼                              ▼                              ▼
    [ Render Managed PostgreSQL ]    [ Render Managed Redis ]    [ S3-Compatible RustFS / MinIO ]
        (Database & Alembic)             (Cache & Sessions)            (Image Artifact Storage)
```

---

## 2. Render Backend Deployment Specification

### 2.1 Service Configuration
- **Service Type:** Web Service
- **Runtime:** Python 3.12
- **Repository:** `https://github.com/Rishit-ui/eggVision`
- **Branch:** `master`
- **Root Directory:** *(Leave blank / repository root)*
- **Build Command:**
  ```bash
  pip install --upgrade pip && pip install -r backend/requirements.txt -r ml/requirements.txt
  ```
- **Start Command:**
  ```bash
  bash scripts/start_render_backend.sh
  ```

### 2.2 Why `scripts/start_render_backend.sh` is Critical
The startup script resolves paths dynamically to guarantee that both `backend/app/` and top-level `ml/` packages reside on `PYTHONPATH` regardless of the directory from which Render invokes the command:
```bash
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
export PYTHONPATH="$BACKEND_DIR:$ROOT_DIR${PYTHONPATH:+:$PYTHONPATH}"
cd "$BACKEND_DIR"
alembic upgrade head
exec python -m uvicorn app.main:app --app-dir "$BACKEND_DIR" --host 0.0.0.0 --port "${PORT:-8000}"
```
This guarantees migrations execute prior to port binding and eliminates `ModuleNotFoundError: No module named 'ml'`.

### 2.3 Required Environment Variables (Render Dashboard)

| Variable Name | Required? | Example / Default Value | Purpose |
| :--- | :---: | :--- | :--- |
| `APP_ENV` | Yes | `production` | Enables production validation rules. |
| `DEBUG` | Yes | `false` | Disables debug logs and detailed error pages. |
| `DATABASE_URL` | Yes | `postgresql+asyncpg://user:pass@dpg-xxx:5432/db` | Internal connection string to Render PostgreSQL. |
| `REDIS_URL` | Yes | `redis://red-xxx:6379` | Internal connection string to Render Redis. |
| `JWT_SECRET` | Yes | *(Min 32 characters random hex)* | Key for signing and verifying JWT tokens. |
| `BOOTSTRAP_TOKEN`| Yes | *(Min 32 characters random hex)* | One-time secret to initialize the admin user. |
| `CORS_ORIGINS` | Yes | `https://egg-vision.vercel.app` | Allowed CORS origins (no wildcards). |
| `S3_ENDPOINT` | Optional | `https://s3.us-east-1.amazonaws.com` | Object storage endpoint URL. |
| `S3_BUCKET` | Optional | `eggvision-artifacts` | Object storage bucket name. |
| `S3_ACCESS_KEY` | Optional | `AKIAIOSFODNN7EXAMPLE` | S3 Access Key ID. |
| `S3_SECRET_KEY` | Optional | `wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY` | S3 Secret Access Key. |
| `S3_REQUIRED` | Yes | `false` | If false, gracefully falls back to local disk if S3 is down. |

---

## 3. Vercel Frontend Deployment Specification

### 3.1 Project Settings
- **Framework Preset:** Next.js
- **Root Directory:** `frontend`
- **Build Command:** `next build` (or `npm run build`)
- **Output Directory:** `.next`
- **Node.js Version:** `20.x`

### 3.2 Authoritative API URL Resolution
The frontend API client (`frontend/src/lib/api.ts`) contains an automated resolver:
```typescript
export const LOCAL_API_BASE_URL = 'http://localhost:8000/api/v1';
export const PRODUCTION_API_BASE_URL = 'https://eggvision-1.onrender.com/api/v1';

export function resolveApiBaseUrl(
  environment = process.env.NODE_ENV,
  configuredUrl = process.env.NEXT_PUBLIC_API_URL
): string {
  const fallback = environment === 'development' ? LOCAL_API_BASE_URL : PRODUCTION_API_BASE_URL;
  return normalizeApiBaseUrl(configuredUrl || fallback);
}
```
**Key Advantage:** Deploying on Vercel requires zero custom environment variables. The production bundle automatically resolves requests to `https://eggvision-1.onrender.com/api/v1`.

---

## 4. Local Development Deployment via Docker Compose

To run the complete EggVision stack locally with one command:

```bash
# 1. Clone repository
git clone https://github.com/Rishit-ui/eggVision.git
cd eggVision

# 2. Configure environment file
cp .env.example .env

# 3. Launch all services
docker compose up -d --build
```

**Service Ports & URLs:**
- Frontend: `http://localhost:3000`
- Backend API Docs: `http://localhost:8000/docs`
- PostgreSQL: `localhost:5432`
- Redis: `localhost:6379`
- RustFS / MinIO Console: `http://localhost:9001`
