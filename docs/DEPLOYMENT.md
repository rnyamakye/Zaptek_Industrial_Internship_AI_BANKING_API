# Deployment on Render

Architecture: **GitHub -> Render Web Service -> FastAPI -> Render PostgreSQL**

## Option A: Blueprint (fastest)
1. Push this repo to GitHub (it contains `render.yaml`).
2. Render dashboard -> **New + -> Blueprint** -> select the repo -> **Apply**.
   This creates the PostgreSQL database and the web service, wires `DATABASE_URL`, generates `SECRET_KEY`.
3. Edit `CORS_ORIGINS` on the service to your frontend origin(s).

## Option B: manual
1. **New + -> PostgreSQL** (note the *Internal Database URL*).
2. **New + -> Web Service** -> connect the GitHub repo.
   - Runtime: Python 3 (or Docker, the repo has a `Dockerfile`)
   - Build command: `pip install -r requirements.txt`
   - Start command: `alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT --proxy-headers --forwarded-allow-ips='*'`
   - Health check path: `/health`
3. Environment variables:

| Variable | Value |
|---|---|
| `ENVIRONMENT` | `production` |
| `SECRET_KEY` | 32+ random characters (`python -c "import secrets; print(secrets.token_urlsafe(48))"`) |
| `DATABASE_URL` | the PostgreSQL URL from step 1 (`postgres://` is fine, it is converted automatically) |
| `CORS_ORIGINS` | comma-separated frontend origins |
| `PYTHON_VERSION` | `3.12.3` |
| `RISK_MODEL_PATH` | optional, path of a trained model bundle |

## After the first deploy
1. Open `https://<your-service>.onrender.com/health` -> `{"status":"healthy","service":"ai-banking-api","version":"1.0.0"}`
2. Swagger UI: `/docs`
3. Create the first admin (Render service -> **Shell**):
   `python -m app.db.create_admin admin@yourbank.com 'StrongPass123' 'Admin Name' 0240000000`
4. Postman: set `baseUrl` to the Render URL, `adminEmail`/`adminPassword`, run the collection in `postman/`.

## Notes
- Migrations run on every deploy (`alembic upgrade head`), so schema changes ship with the code.
- Free-tier services sleep when idle: the first request after a pause can take about 30 seconds.
- Logs (audit events, AI predictions) are written to stdout and appear in the Render **Logs** tab.
- Rate limiting is in memory: fine for one instance; use Redis if you scale to several.
- Refresh tokens are stateless (cannot be revoked before expiry). Suspending a user blocks them immediately.
- Never commit `.env`. Model files in `app/ml/` are allowed by `.gitignore`.

## Running with Docker locally
```bash
docker build -t ai-banking-api .
docker run -p 8000:8000 -e DATABASE_URL=sqlite:///./banking.db ai-banking-api
```
