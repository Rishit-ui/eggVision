# Deploy the EggVision frontend on Vercel

EggVision is a monorepo. Deploy the Next.js application as **one Vercel project** and keep the FastAPI application on a container host such as Render. Do not choose Vercel's multi-service import for this repository: the backend requires migrations, PostgreSQL, Redis, and private object storage.

## Import settings

1. In the repository import screen, select **Import single project** beside `frontend`.
2. Confirm **Root Directory** is `frontend`.
3. Use the automatically detected **Next.js** framework, `npm install`, and `npm run build`.
4. Deploy. Production builds use `https://eggvision-1.onrender.com/api/v1` by default; no Vercel environment variable is required. `NEXT_PUBLIC_API_URL` is only an optional override for a separately hosted preview API and must be a complete URL ending in `/api/v1`.
5. Open `/scan` after signing in. A production browser never falls back to its own `localhost`.

## Backend CORS

Set the backend `CORS_ORIGINS` value to the exact Vercel production URL (and preview URL only if you intend to support previews). Do not use `*` in production. The backend must also have its production configuration and migrations working before you expose the frontend.

## Safety check before attaching a public domain

The public frontend should display `MODEL_NOT_READY` / explicit unavailable states until a trained and validated egg detector and separate defect models are registered. If a Vercel project displays freshness percentages, age estimates, Haugh Units, crack confidence, or “Model v2.4” without evidence, it is not deploying this source and must not be used.
