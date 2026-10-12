# Unified chat and simulated wallet

The customer entry point at `/` and `/send` is one chat. It offers **Make Payment**, **Check Balance**, and **Transaction Details**, and routes typed natural-language requests through the same backend.

## Account sessions

`POST /api/v1/banking/demo-sessions` selects one seeded synthetic profile and returns an opaque, expiring bearer token. The token is hashed in the configured SQL database and bound to one account. Balance, transaction, and chat-session reads/actions verify that binding. The profile picker is intentionally a demo login with no real credential or identity proof; it is only an access-isolation mechanism for synthetic accounts and must not be presented as production authentication.

## Wallet and ledger

When `DATABASE_URL` is configured, PostgreSQL stores demo accounts, sessions, payment records, and ledger entries in APP Shield-prefixed tables. Without it, local demo banking uses transient in-memory SQLite and is cleared when the backend stops. Initial seed balances are read once when each wallet is created:

| Profile | Default opening balance |
| --- | ---: |
| U101 · Alex Morgan | ₹10,000 |
| U102 · Riya Sen | ₹2,000 |
| U103 · Sam Patel | ₹10,000 |

Set `APP_SHIELD_DEMO_BALANCE_U101`, `APP_SHIELD_DEMO_BALANCE_U102`, or `APP_SHIELD_DEMO_BALANCE_U103` in the server process before first startup to change a new wallet's opening balance. Existing wallet rows are authoritative and are not reseeded on restart. `.env.example` documents these values; the project does not automatically load `.env`.

The internal recipient **R207** maps to U102. A confirmed U101-to-R207 payment debits U101, credits U102, writes one payment record and two uniquely constrained ledger entries in one atomic transaction. SQLite uses `BEGIN IMMEDIATE`; PostgreSQL locks wallet rows in a stable order. Any exception rolls back all writes. Repeated confirmation returns the original stored receipt, and unique transaction/idempotency/ledger constraints prevent duplicate payments.

Other recipient catalog entries are not internal wallets. A confirmed simulated payment to them records a sender debit and an `EXTERNAL_SIMULATED` settlement; it does not create or credit an account that is not present in the local wallet table.

Balances, held amounts, transaction history, direction totals, payee filters, date filters, largest debit, and transaction detail are computed from the configured wallet database. Timestamps are stored in UTC; “today” and “this week” use Asia/Kolkata calendar boundaries. Only completed settlements enter the wallet transaction history. A cancelled or failed review remains visible in the current chat with its actual state and creates no ledger entry. Transient local demo state is not migrated; PostgreSQL starts with configured opening balances.

PostgreSQL creates the `app_shield_wallets`, `app_shield_account_aliases`, `app_shield_demo_sessions`, `app_shield_payments`, and `app_shield_ledger_entries` tables. Feedback snapshots, labels, review records, and audit events also use APP Shield-prefixed tables in the same PostgreSQL database. Demo bearer tokens are stored as SHA-256 hashes and expire after 12 hours. Configure the database URL only as a server-side secret; do not use a `VITE_*` variable or commit it.

## Safety boundaries

The existing APP Shield risk engine remains the source for risk decisions and available actions. The chat cannot edit a score or authorize payment. Wallet settlement runs only after the simulator permits continuation and the user explicitly confirms. Balance is checked before review for usability and checked again atomically at settlement. A missing risk service, insufficient funds, or failed database transaction cannot produce a successful receipt.

The data, profile names, balances, account sessions, and transaction records are synthetic. The implementation has no bank connector, external payment rail, government identity provider, or production authentication. See the [API reference](API.md) for the FastAPI routes.
