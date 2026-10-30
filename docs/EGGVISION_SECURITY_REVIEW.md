# EggVision AI — Comprehensive Cybersecurity Review & Hardening Guide
**Document Version:** 1.0.0  
**Classification:** Security Assessment & Threat Model  
**Standards:** OWASP Top 10 (2021), ASVS Level 2, NIST SP 800-53

---

## 1. Threat Modeling & Attack Surface Decomposition

EggVision AI processes multi-part file uploads, manages user authentication tokens, persists relational research data, and interacts with external cloud services. The following threat model evaluates primary attack vectors:

```
[ Attacker / Untrusted Input ]
       │
       ├───► [ Vector 1: Malicious Image Upload ]
       │     - Path traversal via client filename (e.g., "../../etc/passwd")
       │     - Decompression / Decompression Bomb (billion pixels DoS)
       │     - Polyglot executable disguised as JPEG (e.g. PHP/JS payload)
       │
       ├───► [ Vector 2: Authentication & Token Attacks ]
       │     - Weak JWT secrets allowing forged admin signatures
       │     - Unprotected /api/v1/auth/bootstrap account takeover
       │     - Passlib / bcrypt version mismatch denial of service
       │
       └───► [ Vector 3: Data Exfiltration & Log Leakage ]
             - Leaking DB credentials, JWT secrets, or tokens in logs
             - Public unauthenticated streaming of proprietary egg artifacts
             - Overly permissive CORS wildcard headers with credentials
```

---

## 2. Security Controls & Implementation Audit

### 2.1 File Upload Protection (`image_service.py` & `storage_service.py`)
- **Server-Generated Object Keys:** The client-supplied `filename` is **never** used for filesystem writes or S3 keys. The server discards the client filename and generates a cryptographically random UUIDv4 key:
  ```python
  filename = f"{uuid.uuid4()}{extension}"
  ```
- **Strict Path Traversal Guard:** `storage_service._safe_key()` verifies that the sanitized key contains no directory separators (`/`, `\`) or traversal elements (`.`, `..`).
- **Decompression Bomb Protection:** Pillow's pixel limit is enforced (`UPLOAD_MAX_PIXELS = 25_000_000`). Images exceeding 25 megapixels are immediately rejected before full buffer decoding.
- **Canonical MIME & Format Validation:** Rather than trusting the browser `Content-Type` header, Pillow opens the byte stream, decodes the magic bytes, and derives the canonical MIME type and extension (`JPEG`, `PNG`, `WEBP`).
- **Memory Buffer Sizing:** Raw file uploads exceeding `UPLOAD_MAX_SIZE_MB = 10` are rejected with HTTP 413.

### 2.2 Password Hashing & Bcrypt Compatibility
- **Vulnerability History:** Passlib 1.7.4 references `bcrypt.__about__.__version__`. When newer bcrypt versions (4.1.0+) removed `__about__`, password hashing crashed with `AttributeError`.
- **Verified Mitigation:** Pinned `passlib[bcrypt]==1.7.4` and `bcrypt==4.0.1` in `backend/requirements.txt`. Existing database hashes verify correctly, and new hashes use work factor 12.

### 2.3 Bootstrap Endpoint Hardening (`auth.py`)
The initial system setup endpoint `POST /api/v1/auth/bootstrap` is protected by multiple layers:
1. Requires a dedicated, cryptographically strong `BOOTSTRAP_TOKEN` (minimum 32 characters, enforced at startup in production).
2. Verifies that `SELECT count(*) FROM users WHERE role = 'admin'` is 0. If an administrator already exists, the endpoint aborts with HTTP 403.
3. Password complexity enforcement: minimum 12 characters.

### 2.4 CORS Security Configuration
FastAPI's `CORSMiddleware` is configured in `main.py` using `settings.cors_origins`:
- Wildcard `*` origins are strictly prohibited when `allow_credentials=True`. Pydantic validator `validate_cors_origins` in `config.py` rejects wildcard configurations at application startup.
- In production, only the trusted origin `https://egg-vision.vercel.app` is permitted.

### 2.5 Zero Information Leakage Policy
The application codebase was audited to eliminate accidental credential and artifact leakage:
- Log statements use structured, parameterized formats (e.g., `logger.info("scan_stage=image_received request_id=%s", request_id)`).
- Arguments passed to `logger` never include passwords, bearer tokens, full image bytes, or `DATABASE_URL` connection strings.
- Image artifacts stored on S3/RustFS are proxied through the authenticated `/api/v1/artifacts/{key}` route, preventing unauthenticated public scraping of proprietary egg imagery.

---

## 3. Secret Rotation Checklist for Production

If credentials or development secrets were previously committed to version control or displayed in terminal logs, execute the following rotation procedure:

- [ ] **Rotate JWT Secret:** Generate a new 64-character random string (`openssl rand -hex 32`) and update `JWT_SECRET` in the Render dashboard. Existing user sessions will be safely invalidated.
- [ ] **Rotate Bootstrap Secret:** Generate a fresh `BOOTSTRAP_TOKEN` in Render environment settings.
- [ ] **Rotate PostgreSQL Credentials:** In the Render database management console, reset the database user password and update `DATABASE_URL`.
- [ ] **Rotate Object Storage Keys:** Regenerate S3 access keys and secret keys in the cloud storage provider (RustFS / MinIO / AWS S3) and update `S3_ACCESS_KEY` and `S3_SECRET_KEY`.
- [ ] **Verify Production Environment:** Confirm that `APP_ENV=production` and `DEBUG=False` are set on Render.
