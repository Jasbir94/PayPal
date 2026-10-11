# Troubleshooting

## Project folder or drive is unavailable

Open the project from its existing location and check that the drive is unlocked and accessible in Windows File Explorer. `start.bat` reports an inaccessible project folder and does not recreate it. Never paste a BitLocker recovery key into chat or logs.

## Missing Python or backend packages

Install Python 3.11 or later, then from the project root run:

```powershell
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
```

Run `start.bat` again.

## Missing Node.js or frontend packages

Install Node.js 20.19+ or 22.12+ with npm. Then run:

```powershell
cd frontend
npm ci
cd ..
.\start.bat
```

## Incomplete demo data or model files

The initializer creates a dataset only when both synthetic CSVs are absent and trains baseline models only when both baseline model files and their generated reports are absent. If only part of a set exists, it stops and preserves the existing files. Restore the missing files from a trusted copy, or deliberately move the entire synthetic dataset/model set aside before initializing again. Do not use reset or regeneration commands on valuable data.

The remaining scenario, graph, psychology, and fusion artifacts are optional for some fallback paths but should be restored from the project’s trusted saved-model bundle for the full demo.

## Port 8000 or 5173 is occupied

Stop the previous APP Shield session with `stop.bat`. If another program owns either port, close that program or change the ports and matching frontend API proxy in `frontend/vite.config.js`.

## Backend is not ready

Open `http://127.0.0.1:8000/health` for liveness and `/ready` for scoring readiness. Inspect `logs/api.err.log`; model-load messages can explain missing artifacts. The dashboard distinguishes core readiness from optional text-model fallback.

If startup reports that Python asyncio timed out while creating its Windows socket pair, the backend cannot initialize its event loop in that process environment. The launcher now checks this before starting Uvicorn and exits with a specific message instead of waiting for the backend health timeout. Run `start.bat` from a normal local Windows session where Python can use loopback sockets. Do not disable Windows security controls or expose the server on all network interfaces to work around this error. The project does not need an API key for its local synthetic demo.

## Windows pytest reports a blocked SQLAlchemy extension

Some Windows Application Control policies block SQLAlchemy's optional `_processors_cy` compiled extension when pytest imports the SQLite engine. This is a test-runner import problem; the local API startup does not require the database extension. Do not reinstall or replace SQLAlchemy to work around it. From the project root, run:

```powershell
.venv\Scripts\python.exe scripts\run_windows_tests.py -q
```

The wrapper loads SQLAlchemy's bundled `_processors_cy.py` implementation for that Python process only, then runs pytest. It does not edit the virtual environment. APP Shield's normal Windows startup remains `start.bat`; verify its dependency/data preflight independently with:

```powershell
.\scripts\start_app.ps1 -CheckOnly
```

The pure-Python fallback is for test runs only. If the bundled `.py` fallback is missing, the wrapper stops with an explicit error instead of changing installed packages.

## Frontend cannot reach the backend

Confirm both `/ready` and `http://127.0.0.1:5173/` respond. Check `logs/frontend.err.log` and the API proxy in `frontend/vite.config.js`. Retry only after the API reports ready; no simulated payment is executed on an analysis error.

## Generated metrics or report is missing

Check that the input artifacts named in [the research guide](RESEARCH_GUIDE.md) exist. The evaluation runner reports errors rather than substituting fabricated values. Keep the synthetic-data limitation with any metrics you share.
