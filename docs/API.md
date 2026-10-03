# Local API guide

Open `/docs` while the backend is running for the generated OpenAPI reference. Common routes:

| Route | Purpose |
|---|---|
| `GET /health` | Liveness response |
| `GET /ready` | Model/data readiness |
| `GET /api/v1/model-info` | Safe component and model version metadata |
| `GET /api/v1/simulated-payments/scenarios` | Synthetic demo catalog |
| `POST /api/v1/simulated-payments` | Create a simulated attempt (idempotency key required) |
| `POST /api/v1/simulated-payments/{id}/analyze` | Analyze context and optional conversation through the backend |
| `GET /api/v1/simulated-payments/{id}/analyst` | Explain the simulated assessment |
| `POST /api/v1/feedback/{id}/user-action` | Record behavior, never infer fraud truth |
| `POST /api/v1/feedback/{id}/label` | Add a typed, provenance-bearing delayed label |
| `GET /api/v1/feedback/{id}` | Read snapshot/actions/labels/audit history |
| `GET /api/v1/monitoring/summary` | Aggregate-only monitoring summary |
| `GET /api/v1/reviews` | Local analyst review queue |

All payment routes are simulation-only. Do not submit credentials or real payment data. Evidence risk is a bounded score; it should not be interpreted as a real-world probability unless explicitly returned as a calibrated probability for the matching synthetic modality profile.
