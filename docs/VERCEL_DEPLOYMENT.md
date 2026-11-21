# Deploy SpaFlow to Vercel

## What this configuration deploys

`vercel.json` publishes `dist/` as the static frontend and exposes `api/index.py` as a Python Vercel Function. API requests under `/api/*` are rewritten to that function. The function uses the same routes as the local server.

The Python runtime is configured through the root `.python-version`; no third-party dependency installation is required.

## Deploy

1. Import `TranTruongQuocThai/Spa` in Vercel or run `vercel` from the repository root.
2. Framework Preset: **Other**. The repository configuration selects `dist` as the output directory.
3. For a disposable UI/API demonstration only, add `SPAFLOW_DATABASE=/tmp/spaflow_test.sqlite3` under Preview and Production environment variables.
4. Deploy and open `/api/health` to verify the function.

## Critical production limitation

Vercel Function storage is ephemeral. `/tmp/spaflow_test.sqlite3` can be lost on a cold start, a new deployment, or function recycling. It must never hold customer data, payment data, attendance photos, or production credentials.

Before real use, replace the SQLite adapter with a managed database (for example a MySQL/Postgres service) and private object storage for check-in photos. Set connection credentials exclusively in Vercel Environment Variables; do not commit them. Then run migrations and seed only a non-production environment.

## Local verification

```bash
python3 -m unittest discover -s tests -v
python3 server.py --reset-db --port 8765
curl http://localhost:8765/api/health
```
