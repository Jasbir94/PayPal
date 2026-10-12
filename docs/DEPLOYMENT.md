# Public demo deployment

This repository is configured for a **Vercel static frontend + Render FastAPI backend**. Deployments remain synthetic demos: no bank or payment rail is connected.

## Render backend

1. Push this repository to GitHub and connect it in Render with **New → Blueprint**. Render reads the root `render.yaml` file.
2. The Blueprint uses Docker with `backend/Dockerfile` and the repository root (`.`) as its build context. Do not set the Render service Root Directory to `backend/`; the Dockerfile copies `backend/`, `data/`, `saved_models/`, `models/`, `ml/`, `evaluation/`, and `reports/` from the repository root. Uvicorn binds to Render's `PORT` environment variable and `/ready` is the health check.
3. Create a dedicated PostgreSQL database and user for APP Shield. In Render, set the secret `DATABASE_URL` to its rotated PostgreSQL connection string. Do not use credentials pasted into chat or commit a connection string. The API stores synthetic wallets, sessions, payments, ledger entries, analyst feedback, labels, reviews, and audit events in APP Shield-prefixed tables.
4. No persistent Render disk is required. Demo wallets and research feedback persist in PostgreSQL; in-progress chat sessions remain in process memory and reset on restart.
5. Optionally set the Render secret `GEMINI_API_KEY` to a newly rotated Google AI Studio key. `GEMINI_MODEL` defaults to `gemini-2.5-flash`. Keep the key server-side; without it, deterministic chat behavior remains active.
6. Set `APP_SHIELD_CORS_ORIGINS` in the Render service environment to the exact Vercel production origin, for example `https://app-shield-example.vercel.app`. Include only origins that you control; add a preview origin explicitly if needed. Do not append a path or trailing slash.
7. Wait for `/ready` to report `ready`. Verify `/health`, `/ready`, and `/docs` on the Render service URL.

Chat conversations and demo account sessions are held in process memory and disappear on service restart. PostgreSQL-backed wallet and feedback data survive restarts. In-memory conversation state still means this demo should not be scaled to multiple instances or used for production payments.

## Vercel frontend

1. Import the same GitHub repository into Vercel and set **Root Directory** to `frontend`.
2. `frontend/vercel.json` configures `npm ci`, `npm run build`, the `dist` output directory, and an SPA fallback for deep links.
3. In Vercel Project Settings → Environment Variables, add `VITE_API_BASE_URL` with the Render API origin, such as `https://app-shield-api.onrender.com` (no trailing slash). The example value is in `frontend/.env.example`; replace it with the actual Render hostname.
4. Redeploy the frontend after setting or changing this variable. Vite embeds it at build time.
5. Copy the exact Vercel production origin into Render's `APP_SHIELD_CORS_ORIGINS`, then redeploy/restart the backend if needed.

In local development, leave `VITE_API_BASE_URL` unset. Vite keeps using the existing proxy to `127.0.0.1:8000`.

## Smoke test after deployment

1. Open the Vercel URL and confirm the demo account picker loads.
2. Check balance and transaction history; verify the API's `/api/v1/banking/*` calls succeed from the deployed origin.
3. Run a low-risk simulated payment through review and explicit confirmation. Verify the receipt and updated balance/history.
4. Run a synthetic scam demo and verify the backend warning, evidence, and action policy. No real funds are transferred.
5. Confirm Render `/health` and `/ready` return healthy/ready and inspect logs for CORS or database-path errors.

## Local validation

```powershell
cd frontend
npm ci
npm test
npm run build
```

To verify that a separately hosted backend URL is embedded in the bundle, set `VITE_API_BASE_URL` in the Vercel build environment and inspect the build output. Never put secrets in a `VITE_*` variable: values with that prefix are public in the browser bundle.

No API key is needed for the current local retrieval/templates and synthetic payment flow.

## Hosting platform documentation

- [Render Blueprint specification](https://render.com/docs/blueprint-spec)
- [Render persistent disks and their single-instance limitation](https://render.com/docs/disks)
- [Render free-service limitations](https://render.com/docs/free)
- [Vercel Vite deployment](https://vercel.com/docs/frameworks/frontend/vite)
- [Vercel project configuration](https://vercel.com/docs/project-configuration/vercel-json)
