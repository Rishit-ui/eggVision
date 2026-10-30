# EggVision AI — System Administrator & Operations Manual
**Document Version:** 1.0.0  
**Target Audience:** Cloud Engineers, DevOps Administrators, Research IT Supervisors

---

## 1. Initial System Bootstrap & Account Provisioning

When deploying an EggVision instance for the first time, no default administrative accounts exist in the database.

### 1.1 Running the Bootstrap Request
The administrator must invoke the one-time bootstrap endpoint with the server-configured `BOOTSTRAP_TOKEN`:

```bash
curl -X POST "https://eggvision-1.onrender.com/api/v1/auth/bootstrap" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@eggvision.org",
    "password": "StrongAdminPassword123!",
    "bootstrap_token": "<YOUR_CONFIGURED_BOOTSTRAP_TOKEN>"
  }'
```

### 1.2 Bootstrap Security Invariants
- The password must be at least 12 characters in length.
- The endpoint queries `SELECT count(*) FROM users WHERE role = 'admin'`. If an administrator already exists, it rejects the request with HTTP 403 Forbidden.
- Once bootstrap succeeds, the initial administrator can log in via `/login` and access the Administration Console (`/admin`).

---

## 2. User & Role Management

EggVision implements Role-Based Access Control (RBAC):
- **`admin`**: Full system permissions, user management, audit log inspection, batch creation, and model registration.
- **`researcher`**: Scan ingestion, capture report review, batch editing, sensor reading entry, and ground-truth recording.
- **`user`**: Basic scan capture submission and personal history viewing.

---

## 3. Operational Monitoring & Health Diagnostics

Administrators can monitor the live operational status of all infrastructure components via `GET /api/v1/health`:

```bash
curl -s "https://eggvision-1.onrender.com/api/v1/health" | jq .
```

### Component Status Interpretation
- **`database`**: Checks connection to PostgreSQL and executes `SELECT 1`. If `error`, check Render PostgreSQL dashboard for connection exhaustion or firewall rules.
- **`redis`**: Pings Redis via `client.ping()`. If `error`, check `REDIS_URL` credentials.
- **`storage`**:
  - `ok`: Object storage bucket is accessible and writable.
  - `degraded`: Object storage is unconfigured or unreachable; system is currently operating in local disk fallback mode.
  - `error`: Neither object storage nor local disk is writable.
- **`model_service`**:
  - `not_ready`: Expected baseline state. Transparently informs operators that no trained neural network weights are active.
  - `ok`: A validated model checkpoint is loaded.

---

## 4. Disaster Recovery & Backup Procedures

### 4.1 PostgreSQL Database Backups
To take an encrypted, consistent logical backup of the production database:
```bash
# Export schema and all records
pg_dump -U eggvision -h <RENDER_PG_HOST> -p 5432 -d eggvision -F c -b -v -f "eggvision_backup_$(date +%Y%m%d).dump"
```

### 4.2 Restoring from Backup
```bash
# Restore to a clean database target
pg_restore -U eggvision -h <TARGET_PG_HOST> -p 5432 -d eggvision -v "eggvision_backup_20261030.dump"
```

### 4.3 Handling Render Free Tier Sleep & Cold Starts
On Render's free tier, backend instances spin down after 15 minutes of inactivity:
- A cold-start wake-up request can take 30 to 50 seconds.
- The frontend client is configured with bounded 20s timeouts and distinct error reporting.
- To prevent daytime cold starts in production laboratories, configure a lightweight synthetic HTTP monitor (e.g. UptimeRobot or Cron) invoking `GET /api/v1/health` once every 10 minutes.
