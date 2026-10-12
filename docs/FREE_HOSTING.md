# Free demo hosting

The free preview uses a Vercel frontend, a Render Python API, and a PostgreSQL database for durable demo wallet and payment data. This is for a personal synthetic demo, not a production payment service.

## What persists

- PostgreSQL stores demo profiles, sessions, simulated payment records, wallet ledger entries, analyst feedback, and audit records through `DATABASE_URL`.
- Local filesystem persistence is not used. In-progress chat sessions remain in memory and reset when the free Render service sleeps, restarts, or redeploys.
- The paid `render.yaml` deployment is separate. Existing local SQLite records are not automatically imported into PostgreSQL.

Render free services sleep after 15 minutes without traffic and can take about a minute to wake. Free instances have 512 MB RAM and share a monthly 750 free-instance-hour allowance per workspace. Select a PostgreSQL provider and plan appropriate for demo data; these services are not suitable for production banking data.

## Create the API service

1. Rotate the database credential pasted into chat. Create a dedicated PostgreSQL database/user for APP Shield; do not reuse credentials from another project.
2. In Render, create a Blueprint from `https://github.com/Jasbir94/PayPal` and select `render-free.yaml` as its Blueprint file. This creates a separate service named `app-shield-api-free` on the free plan; it does not alter the existing paid Blueprint.
3. Set the Blueprint secret `DATABASE_URL` to the new PostgreSQL connection string. Never put it in source code or a `VITE_*` variable.
4. Deploy and wait for `/ready` to return `ready`. Check `/health`, `/docs`, and the Render logs.

## Create the frontend site

1. Import the same GitHub repository into Vercel and set **Root Directory** to `frontend`.
2. Add `VITE_API_BASE_URL` as an environment variable with the new Render API origin, such as `https://app-shield-api-free.onrender.com` (no trailing slash), then deploy.
3. Set `APP_SHIELD_CORS_ORIGINS` in the Render service to the exact Vercel production origin, without a trailing slash, and redeploy the API.
4. From the hosted frontend, test account setup, balance, transaction history, a reviewed low-risk payment, explicit confirmation, cancellation, and a high-risk warning. All payments remain simulated.

## Limits and references

- [Render free services](https://render.com/docs/free)
- [Render Blueprint configuration](https://render.com/docs/infrastructure-as-code)
- [Vercel Hobby plan](https://vercel.com/docs/plans/hobby)
- [Render PostgreSQL](https://render.com/docs/databases)
- [Neon PostgreSQL connection strings](https://neon.tech/docs/connect/connect-from-any-app)
