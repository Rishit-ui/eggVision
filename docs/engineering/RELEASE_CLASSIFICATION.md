# EggVision — Release Classification

**Branch:** `codex/eggvision-fix-frontend-build`
**Date:** 2026-11-13 (Asia/Kolkata)
**Reviewer:** Autonomous Engineering Agent (Antigravity)

---

## Release Readiness Table

| Level | Status | Evidence |
|:------|:-------|:---------|
| **1. Engineering-Ready** | ✅ **PASS** | 102/102 pytest tests pass (0 failures, 0 warnings). Coverage: 80.7% (1,995 / 2,472 lines). Ruff linting clean (0 errors, all E402 noqa annotations correct). Type-check clean. pip check clean. Next.js production build: 12/12 routes compiled cleanly. OpenAPI schema generated. Protected research data integrity verified before and after verification run. |
| **2. Pilot-Ready** | ✅ **PASS** | End-to-end scan pipeline functional: multipart upload → content validation → OpenCV candidate screening → quality assessment → contour segmentation → vertical CLAHE normalisation → database persistence → scan result retrieval. `MODEL_NOT_READY` returned honestly by inference endpoint. Health endpoints `/health/live` (200 alive) and `/health/ready` (200 ready) added and verified. CORS restricted to localhost in dev, forbids wildcard domains in all environments, enforces explicit HTTPS origins in production. Security headers applied on every response. Upload size/pixel limits enforced. Directory-traversal prevention in storage service. Sliding-window login rate limiting with `X-Forwarded-For` proxy IP extraction. Role-based server-side admin protection on `/admin/users`. |
| **3. Model-Validated** | ❌ **BLOCKED** | Zero eligible intact shell-on egg images exist in repository. `PlaceholderEngine` correctly returns `MODEL_NOT_READY`. Ontology defined in `ml/ontology.yaml` (6 defect classes). **What is needed:** physical intact shell-on eggs captured under controlled candling optics; paired destructive lab measurements (albumen height, Haugh Unit); reviewed annotations following `ml/ontology.yaml`; reproducible training + evaluation run. |
| **4. Scientific-Ready** | ❌ **BLOCKED** | Haugh Unit freshness scoring requires destructive breakout lab protocol (physical equipment, trained operator, traceable measurements). No surrogate is scientifically valid without paired empirical ground truth. |
| **5. Security-Audited** | ✅ **PASS** | Dedicated security test suite (`tests/backend/test_security_audit.py`) passes 9/9 checks. JWT secret is flagged insecure for production at startup. `AUTH_REQUIRED=false` in dev; production validator enforces `true`. CORS wildcard explicitly forbidden. Upload content-type and pixel limits enforced. Presigned URL scoped to `ContentType`, expires in 300 s. Storage key sanitised (directory-traversal blocked). Sliding-window rate limiter active on `/auth/login`. Server-side admin role check enforced on `/admin/users`. No secrets logged. |
| **6. Deployment-Ready** | ❌ **BLOCKED** | **Render:** Web service (`https://eggvision-1.onrender.com`) is running a pre-failure legacy build; the latest deploy on `master` failed exit status 255 because `%(here)s/alembic` fix (commits `3c7721ba`, `4c5da8d2`) remains unmerged on `codex/eggvision-fix-frontend-build`. **Vercel:** `https://egg-vision.vercel.app` and preview URLs return HTTP 404 (DEPLOYMENT_NOT_FOUND). Live production deployment requires merging the fix to `master` and configuring provider secrets. |

---

## Security Audit Summary

| Area | Finding | Status |
|:-----|:--------|:-------|
| JWT secret | Default value blocked in production by startup validator | ✅ PASS |
| Auth enforcement | `AUTH_REQUIRED` validated to be `true` in production | ✅ PASS |
| CORS | Wildcard origins rejected by validator; origins must be explicit http(s) | ✅ PASS |
| Upload size | `UPLOAD_MAX_SIZE_MB` (default 20 MB) enforced in image_service | ✅ PASS |
| Upload pixel limit | `UPLOAD_MAX_PIXELS` (25 MP) enforced | ✅ PASS |
| Content-type validation | JPEG/PNG/WebP only; extension and content-type both checked | ✅ PASS |
| Storage key sanitisation | `_safe_key()` strips traversal sequences (`..`, `//`, backslash) | ✅ PASS |
| Presigned URL | Scoped to `ContentType`, 300 s expiry | ✅ PASS |
| Security headers | `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`, HSTS (production only) | ✅ PASS |
| Secrets in logs | JWT tokens, passwords not logged | ✅ PASS |
| `DEBUG` in production | Startup validator blocks `DEBUG=true` in production | ✅ PASS |
| Cookie token fallback | Accepted alongside Bearer header; no HttpOnly flag set server-side (frontend responsibility) | ℹ️ NOTE |

---

## Dataset Eligibility Assessment

| Dataset | Files | Filter Decision | Training Eligibility |
|:--------|:------|:----------------|:--------------------|
| `ml/data/raw/` | 5 images (Open Images, CC BY 2.0) | 3× cooked egg / egg dish, 1× egg dish, 1× egg in carton | ❌ **Not eligible** — all 5 reviewed and labelled as cooked/prepared/carton; none are intact shell-on eggs |
| `ml/data/intact_egg_candidates/` | 0 files | — | ❌ **Empty** — no images |
| `ml/data/ambiguous/` | 0 files | — | ❌ **Empty** |
| `ml/data/custom_collection/` | README only | — | ❌ **No images collected yet** |
| `ml/data/cooked_eggs/`, `egg_dishes/`, `egg_cartons/` | (not enumerated) | Out-of-distribution negative examples only | ❌ **Not eligible** as positive training examples for intact-egg detector |
| `ml/data/out_of_distribution/` | — | Negative examples | ❌ **Not eligible** as positive examples |

**Summary:** Zero eligible training images exist for any ML task (egg detection, segmentation, defect classification, Haugh Unit regression). The training infrastructure is in place but cannot be run without first completing the physical data collection protocol described in `ml/data/custom_collection/README.md`.

---

## Docker Status

Docker CLI v29.8.2 is installed but the Docker Engine daemon is not running (`open //./pipe/docker_engine: The system cannot find the file specified`). Docker config file access is denied (`C:\Users\Rishit\.docker\config.json: Access is denied`).

**Impact:** Docker image builds and compose smoke tests cannot be executed in this environment. The Dockerfiles and compose configuration are syntactically correct (reviewed) and are exercised in CI on GitHub Actions (Linux runner).

---

## Remaining Hard Blockers (Require External Action)

1. **Physical egg specimens + candling chamber** — cannot be provided by software.
2. **Destructive lab measurements** (albumen height, Haugh Unit) — cannot be fabricated.
3. **Reviewed ML annotations** (YOLO bounding boxes for intact eggs) — requires human reviewers and physical data.
4. **Cloud deployment credentials** (Supabase DB URL, Supabase S3 keys, Vercel project token) — must be provided by the authorized deployment owner.
5. **Docker daemon** — requires the user to start Docker Desktop or the Docker Engine service.

---

## Alembic Migration Note

`backend/alembic.ini` references `script_location = %(here)s/alembic` (using Alembic's `%(here)s` directive to resolve relative to `alembic.ini`'s folder, ensuring migrations can be run both from the repository root as `alembic -c backend/alembic.ini` and from inside `backend` as `alembic -c alembic.ini` without path resolution errors on deployment platforms such as Render). `backend/alembic/env.py` injects `backend/` onto `sys.path` at load time with `# noqa: E402` to avoid ruff false positives.

To run migrations against a live Postgres instance:

From repository root:
```powershell
$env:DATABASE_URL = "postgresql+asyncpg://user:pass@host:5432/dbname"
backend\.venv\Scripts\python.exe -m alembic -c backend\alembic.ini upgrade head
```

From inside `backend`:
```powershell
$env:DATABASE_URL = "postgresql+asyncpg://user:pass@host:5432/dbname"
.\.venv\Scripts\python.exe -m alembic -c alembic.ini upgrade head
```

---

## CI/CD Workflow Changes

`.github/workflows/ci.yml` updated to:
- Trigger on `master`, `main`, and `codex/**` branches (was `main` only).
- Include `ml/tests/` in the pytest invocation.
- Include `npm run lint` step in the frontend job.
- Set `PYTHONPATH` correctly for the lint step as well as the test step.

---

## Final Classification

> **EggVision is Engineering-Ready and Pilot-Ready.**
> It is NOT Model-Validated, Scientific-Ready, or fully Deployment-Ready.
> No placeholder inference is presented as a working AI model anywhere in the codebase.
> The release candidate branch (`codex/eggvision-fix-frontend-build`) is ready for review and merge to `master` once the authorized owner approves.
