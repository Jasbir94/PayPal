# Quick start

APP Shield is a local synthetic payment-analysis demo. It does not connect to a bank and never transfers real money.

## Windows

Install Python 3.11 or later and Node.js 20.19+ or 22.12+ (with npm), then open PowerShell in the project folder and run:

```powershell
.\start.bat
```

On first run, the launcher checks dependencies, creates demo data only when both data files are absent, and trains baseline models only when both baseline models and their reports are absent. It refuses to overwrite an incomplete set. It starts the API and frontend, checks readiness, and opens the unified customer chat.

- Control center: <http://127.0.0.1:5173/>
- API health: <http://127.0.0.1:8000/health>
- API readiness: <http://127.0.0.1:8000/ready>
- API reference: <http://127.0.0.1:8000/docs>

Stop only APP Shield's own backend/frontend processes with `stop.bat`. Startup logs are written to `logs/`.
Use `start.bat -NoBrowser` to start and verify both services without opening a browser, or `start.bat -CheckOnly` to run dependency/data checks only.

## Manual startup (macOS/Linux or development terminals)

Use Python 3.11+, Node.js 20.19+ or 22.12+, and npm. From the project root:

```bash
python -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.txt
.venv/bin/python -m scripts.initialize_demo
```

In one terminal, run the API:

```bash
.venv/bin/python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

In another terminal:

```bash
cd frontend
npm ci
npm run dev -- --host 127.0.0.1 --strictPort
```

On Windows, replace `.venv/bin/python` with `.venv\Scripts\python.exe`.

## Use the customer chat

The chat opens with three actions: **Make Payment**, **Check Balance**, and **Transaction Details**. You can also type requests such as “Send ₹3,000 to Riya Sen,” “What's my balance?” or “How much did I send this week?”

For a payment, the backend checks the recipient and available balance, runs the APP Shield assessment, asks any selected context question, and shows a review. A separate **Confirm & Send** action is required. Internal demo-recipient transfers update both wallets and append debit/credit ledger rows atomically. Other catalog recipients are simulated external settlements and are not credited to a fabricated local wallet.

The account picker switches among synthetic profiles. On a new database, U101 starts with ₹10,000 and U102 starts with ₹2,000; set `APP_SHIELD_DEMO_BALANCE_U101` / `APP_SHIELD_DEMO_BALANCE_U102` before first startup to change those seed amounts. Balance changes persist in `data/processed/demo_banking.sqlite3`. These profile sessions are for a local demo and do not prove real-world identity. See [simulated banking details](BANKING_DEMO.md). For a prepared fraud case, analyst and research routes remain available directly.
