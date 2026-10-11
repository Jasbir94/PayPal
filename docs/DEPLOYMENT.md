# Public demo deployment

This repository is configured for a **Vercel static frontend + Render FastAPI backend**. Deployments remain synthetic demos: no bank or payment rail is connected.

## Render backend

1. Push this repository to GitHub and connect it in Render with **New → Blueprint**. Render reads the root `render.yaml` file.
2. The Blueprint installs `backend/requirements.txt`, validates the committed synthetic datasets/models, starts Uvicorn on Render's `$PORT`, and uses `/ready` as its health check.
3. Create a dedicated MongoDB database named `appshield` and a database user scoped to that database. In Render, set the secret `APP_SHIELD_MONGO_URI` to its MongoDB Atlas connection string and keep `APP_SHIELD_MONGO_DATABASE=appshield`. Never use a URI for another application or commit a connection string. MongoDB stores synthetic wallets, demo sessions, payment records, and ledger entries. The API uses atomic multi-document transactions, so use Atlas or another replica-set deployment.
4. The Blueprint retains a 1 GB disk at `/var/data` for analyst feedback/research SQLite records. This still requires a paid Render web-service plan. Render Free services do not support persistent disks, and their local files are lost when they restart or redeploy. The Mongo wallet database and feedback database are separate.
5. Set `APP_SHIELD_CORS_ORIGINS` in the Render service environment to the exact Vercel production origin, for example `https://app-shield-example.vercel.app`. Include only origins that you control; add a preview origin explicitly if needed. Do not append a path or trailing slash.
6. Wait for `/ready` to report `ready`. Verify `/health`, `/ready`, and `/docs` on the Render service URL.

The feedback database disk intentionally pins this demo API to one instance. Render documents that a service with a persistent disk cannot scale to multiple instances. Chat conversations are held in process memory and disappear on service restart. Mongo-backed wallets survive restarts, but demo sessions and in-progress chats do not. Do not use this setup for production payments or multi-instance traffic.

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
