# EggVision — Required Environment Variables

## Vercel Backend Project (Python Function)

Set these in Vercel Dashboard → Project Settings → Environment Variables.
All are required for production unless marked optional.

| Variable | Description | Example |
|---|---|---|
| `DATABASE_URL` | Supabase Supavisor **transaction** pooler URL (port 6543) | `postgresql+asyncpg://postgres.xxxx:PASSWORD@aws-0-ap-south-1.pooler.supabase.com:6543/postgres` |
| `REDIS_URL` | Upstash Redis TLS URL | `rediss://default:TOKEN@global-xxx.upstash.io:6379` |
| `S3_ENDPOINT` | Supabase Storage S3 endpoint | `https://xxxx.supabase.co/storage/v1/s3` |
| `S3_BUCKET` | Supabase Storage bucket name | `eggvision` |
| `S3_ACCESS_KEY` | Supabase project S3 access key ID | `xxxx` |
| `S3_SECRET_KEY` | Supabase project S3 secret access key | `xxxx` |
| `S3_REGION` | Always `us-east-1` for Supabase | `us-east-1` |
| `JWT_SECRET` | Random 64-char secret for signing tokens | `openssl rand -hex 32` |
| `BOOTSTRAP_TOKEN` | One-time admin account creation token (≥32 chars) | `openssl rand -hex 32` |
| `CORS_ORIGINS` | Exact Vercel frontend origin (no trailing slash) | `https://egg-vision.vercel.app` |
| `APP_ENV` | Must be `production` | `production` |
| `DEBUG` | Must be `false` | `false` |
| `AUTH_REQUIRED` | Must be `true` | `true` |
| `S3_REQUIRED` | Must be `true` | `true` |
| `DIRECT_UPLOAD_ENABLED` | Enable presigned-URL upload for large images | `true` |
| `UPLOAD_MAX_SIZE_MB` | Max upload size in MB | `20` |
| `DB_POOL_SIZE` | SQLAlchemy pool size (keep ≤2 for serverless) | `2` |
| `DB_MAX_OVERFLOW` | Pool overflow | `0` |

## Vercel Frontend Project (Next.js)

| Variable | Description | Example |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | URL of the Vercel backend project | `https://eggvision-api.vercel.app/api/v1` |

## Free-tier limits visible in this configuration

| Service | Free tier limit |
|---|---|
| Vercel Hobby | 100 GB-hours/month, 100 deployments/day, 12 serverless invocations/sec |
| Vercel Function | 300s max duration, 1024 MB memory |
| Supabase Free | 500 MB PostgreSQL, 1 GB Storage, 5 GB bandwidth, 2 million DB rows |
| Upstash Free Redis | 10,000 commands/day, 256 MB data |
