# AI-Powered Banking API

FastAPI backend with JWT auth, role-based access, banking operations and an AI risk-assessment service.
Training project: uses synthetic data only, never real customer financial information.

## Run locally
```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```
Swagger docs: http://localhost:8000/docs  ·  Health: http://localhost:8000/health

## Run tests
```bash
pytest
```

## Layout
```
app/
  main.py            app + router wiring + /health
  core/              config, security
  db/                engine, session, Base
  models/            SQLAlchemy models (10 entities)
  schemas/           Pydantic request/response schemas
  api/routers/       one file per resource
  services/          business logic, incl. ai_risk_service.py
  ml/                model artifacts (risk_model.pkl when available)
tests/               pytest + FastAPI TestClient, isolated in-memory DB
docs/                ENDPOINTS.md (API contract), OWNERSHIP.md (who owns what)
```

## AI risk model
`app/services/ai_risk_service.py` uses a rule-based placeholder (`rules-0.1`) until a trained model
is placed at `RISK_MODEL_PATH`. The trained model is a demo trained on synthetic data.

## Team workflow
See `docs/OWNERSHIP.md`. Agree API shapes in `docs/ENDPOINTS.md` before coding.

## Deployment (Render)
To be completed by Rick: env vars, PostgreSQL, migrations, start command, health check.
