# Deploy the EggVision frontend on Vercel

EggVision is a monorepo. Deploy the Next.js application as **one Vercel project** and keep the FastAPI application on a container host such as Render. Do not choose Vercel's multi-service import for this repository: the backend requires migrations, PostgreSQL, Redis, and private object storage.

## Import settings

1. In the repository import screen, select **Import single project** beside `frontend`.
2. Confirm **Root Directory** is `frontend`.
3. Use the automatically detected **Next.js** framework, `npm install`, and `npm run build`.
4. In **Project Settings → Environment Variables**, add `NEXT_PUBLIC_API_URL` with the complete public API base URL, for example `https://your-render-service.onrender.com/api/v1`. Apply it to Production and Preview if previews should call that backend.
5. Deploy, then open `/scan`. If the API URL is missing, the frontend will now show a configuration error instead of silently calling a visitor's `localhost`.

## Backend CORS

Set the backend `CORS_ORIGINS` value to the exact Vercel production URL (and preview URL only if you intend to support previews). Do not use `*` in production. The backend must also have its production configuration and migrations working before you expose the frontend.

## Safety check before attaching a public domain

The public frontend should display `MODEL_NOT_READY` / explicit unavailable states until a trained and validated egg detector and separate defect models are registered. If a Vercel project displays freshness percentages, age estimates, Haugh Units, crack confidence, or “Model v2.4” without evidence, it is not deploying this source and must not be used.
