# Free demo hosting

The lowest-friction free setup for this repository is a Vercel frontend, a Render Python API, and MongoDB Atlas for durable demo wallet and payment data. This is for a personal synthetic demo, not a production payment service.

## What persists

- MongoDB stores demo profiles, account sessions, simulated payment records, and wallet ledger entries when `APP_SHIELD_MONGO_URI` is set.
- The free Render service has an ephemeral filesystem. Analyst feedback/audit/review history uses `/tmp/feedback.sqlite` and can disappear when the service sleeps, restarts, or redeploys. In-progress chat sessions are in memory and also reset on restart.
- The separate paid `render.yaml` deployment and its persistent disk are left unchanged. The free service is a new deployment and does not import existing SQLite records.

Render free services sleep after 15 minutes without traffic and can take about a minute to wake. Free instances have 512 MB RAM and share a monthly 750 free-instance-hour allowance per workspace. Atlas Free clusters have a 512 MB storage limit and no backups. These services are suitable for a demo, not production data.

## Create the API service

1. Rotate the MongoDB database-user password that was pasted into chat. Create a new database user with access limited to the `appshield` database. Do not reuse the credentials for another project.
2. In Render, create a Blueprint from `https://github.com/Jasbir94/PayPal` and select `render-free.yaml` as its Blueprint file. This creates a separate service named `app-shield-api-free` on the free plan; it does not alter the existing paid Blueprint.
3. Set the Blueprint secret `APP_SHIELD_MONGO_URI` to the newly rotated Atlas connection string. `APP_SHIELD_MONGO_DATABASE` is set to `appshield` in the file. Atlas connections need the Render service’s outbound address to be accepted; use a narrowly scoped access list if your hosting setup provides stable egress. Never put the URI in source code or a `VITE_*` variable.
4. Deploy and wait for `/ready` to return `ready`. Check `/health`, `/docs`, and the Render logs. Atlas must support replica-set transactions; Atlas clusters do.

## Create the frontend site

1. Import the same GitHub repository into Vercel and set **Root Directory** to `frontend`.
2. Add `VITE_API_BASE_URL` as an environment variable with the new Render API origin, such as `https://app-shield-api-free.onrender.com` (no trailing slash), then deploy.
3. Set `APP_SHIELD_CORS_ORIGINS` in the Render service to the exact Vercel production origin, without a trailing slash, and redeploy the API.
4. From the hosted frontend, test account setup, balance, transaction history, a reviewed low-risk payment, explicit confirmation, cancellation, and a high-risk warning. All payments remain simulated.

## Limits and references

- [Render free services](https://render.com/docs/free)
- [Render Blueprint configuration](https://render.com/docs/infrastructure-as-code)
- [Vercel Hobby plan](https://vercel.com/docs/plans/hobby)
- [MongoDB Atlas free-cluster limits](https://www.mongodb.com/docs/atlas/reference/limitations/)
- [MongoDB connection setup](https://www.mongodb.com/docs/atlas/connect-to-database-deployment/)
