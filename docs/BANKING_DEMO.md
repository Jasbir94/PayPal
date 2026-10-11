# Unified chat and simulated wallet

The customer entry point at `/` and `/send` is one chat. It offers **Make Payment**, **Check Balance**, and **Transaction Details**, and routes typed natural-language requests through the same backend.

## Account sessions

`POST /api/v1/banking/demo-sessions` selects one seeded synthetic profile and returns an opaque, expiring bearer token. The token is hashed in the SQLite database and bound to one account. Balance, transaction, and chat-session reads/actions verify that binding. The profile picker is intentionally a demo login with no real credential or identity proof; it is only an access-isolation mechanism for local synthetic accounts and must not be presented as production authentication.

## Wallet and ledger

The ledger is stored in `data/processed/demo_banking.sqlite3` by default, or the path in `APP_SHIELD_BANKING_DB`. Initial seed balances are read once when each wallet is created:

| Profile | Default opening balance |
| --- | ---: |
| U101 · Alex Morgan | ₹10,000 |
| U102 · Riya Sen | ₹2,000 |
| U103 · Sam Patel | ₹10,000 |

Set `APP_SHIELD_DEMO_BALANCE_U101`, `APP_SHIELD_DEMO_BALANCE_U102`, or `APP_SHIELD_DEMO_BALANCE_U103` in the server process before first startup to change a new wallet's opening balance. Existing wallet rows are authoritative and are not reseeded on restart. `.env.example` documents these values; the project does not automatically load `.env`.

The internal recipient **R207** maps to U102. A confirmed U101-to-R207 payment debits U101, credits U102, writes one payment record and two uniquely constrained ledger entries inside one SQLite `BEGIN IMMEDIATE` transaction. Any exception rolls back all writes. A concurrent debit rechecks the available balance under the write lock. Repeated confirmation returns the original stored receipt, and the ledger's transaction/account/direction uniqueness constraint prevents duplicate rows.

Other recipient catalog entries are not internal wallets. A confirmed simulated payment to them records a sender debit and an `EXTERNAL_SIMULATED` settlement; it does not create or credit an account that is not present in the local wallet table.

Balances, held amounts, transaction history, direction totals, payee filters, date filters, largest debit, and transaction detail are computed from SQLite rows. Timestamps are stored in UTC; “today” and “this week” use Asia/Kolkata calendar boundaries. Only completed settlements enter the wallet transaction history. A cancelled or failed review remains visible in the current chat with its actual state and creates no ledger entry.

## Safety boundaries

The existing APP Shield risk engine remains the source for risk decisions and available actions. The chat cannot edit a score or authorize payment. Wallet settlement runs only after the simulator permits continuation and the user explicitly confirms. Balance is checked before review for usability and checked again atomically at settlement. A missing risk service, insufficient funds, or failed database transaction cannot produce a successful receipt.

The data, profile names, balances, account sessions, and transaction records are synthetic. The implementation has no bank connector, external payment rail, government identity provider, or production authentication. See the [API reference](API.md) for the FastAPI routes.
